"""What is left of Cerebras' rate limits, and the throttle that keeps us inside them.

Measured against the real API on 2026-08-26, with `gemma-4-31b` and a second model, and
re-measured on 2026-08-29 when the throttle turned out not to be throttling:

- Every response carries `x-ratelimit-{limit,remaining}-{requests,tokens}-{minute,hour,day}`
  and **no `reset` header at all**, so the window has to be reconstructed from our own call
  timestamps. That is what this module is: a rolling ledger.
- NO header states the ceiling this ledger enforces: the four `CEREBRAS_MAX_*` settings do,
  and nothing may raise them. `limit-*` reports the MODEL's published quota (gemma: 500
  req/min, 250 000 uncached tok/min), and `remaining-*` was measured on 2026-08-26 counting
  down from the ACCOUNT's much smaller one (5 req/min, 2 400 req/day) — but re-measured on
  2026-08-29 it counts down from the model's too (719 998 of 720 000 requests a day). That
  reading used to be trusted to RAISE a ceiling, on the argument that more left than the
  settings claim can only mean a bigger account; what it actually meant was that the first
  answer of every installation lifted the ceilings to the catalogue's and the throttle never
  held another call. A header may only ever LOWER what we believe is left.
- The buckets are **per model**: a call to the second model left `remaining-requests-day` at 2399 and
  the next call to gemma reported 2399 as well, each against its own 2 400.
- The request counters are exact; the token counters lag. A 74-token call and a 20-token
  call each moved `remaining-tokens-day` by exactly 6. So `usage` — which is exact and
  arrives with the answer — is what this ledger counts, and a header may only ever LOWER
  what we believe is left, never raise it.

The ledger is a file because builds run in `server.jobs.build_worker`, a separate process,
and they are precisely what empties a daily budget. It used to lean on the queue for the
rest — one job at a time meant two processes never called at once — and that assumption
went when the remote lane got a capacity, so both halves of it are guarded here now:

- **Every read-modify-write is one transaction**, held against other threads with a lock and
  against other processes with `flock` on a sidecar file. The lock cannot live on the ledger
  itself: `write_json` replaces it through a `.tmp`, so the inode a waiter is holding is not
  the inode the writer leaves behind — and two unguarded writers collide on that `.tmp`,
  which corrupts the file rather than merely losing a count.
- **The gate BOOKS what it lets through.** Checking and then calling is not a throttle when
  two callers can check at once: both read the same room and both spend it. So `wait`
  returns a `Claim` and writes the call into the ledger at its estimate before it goes out,
  and `record` replaces that estimate with the exact `usage` when the answer lands. A claim
  nobody settles — a process that died mid-call — ages out with the inflight entries.
"""

import json
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

try:  # POSIX only, and the only thing that makes the file safe between processes.
    import fcntl
except ImportError:  # pragma: no cover - this project runs on Linux
    fcntl = None

from loguru import logger

from .. import config
from . import progress
from .inference import InferenceError
from .json_io import write_json

# The two windows worth enforcing. The hour is deliberately absent: measured, it never binds
# before the minute and the day do — gemma reported 44 999 994 tokens left of the hour while
# the day sat at 999 994 of 1 000 000.
WINDOWS: tuple[tuple[str, str, float], ...] = (
    ("minute", "por minuto", 60.0),
    ("day", "por día", 86_400.0),
)

# Roughly what a character costs across the pipeline's Spanish prompts. It only has to be
# good enough to gate one call ahead: `record` replaces it with the exact `usage` the answer
# carries, so an error here is corrected within the same call and never accumulates.
CHARS_PER_TOKEN = 4.0
_REQUEST_OVERHEAD_TOKENS = 32

# A call in flight that nobody closed belongs to a process that died. The engine's own read
# timeout is 600 s, so nothing legitimate outlives it.
_INFLIGHT_STALE_SECONDS = 600.0


class BudgetExhausted(InferenceError):
    """The window will not free up soon enough to be worth waiting for."""


@dataclass(frozen=True)
class Claim:
    """Room booked in the ledger for one call, before that call goes out.

    It is what makes the throttle hold with several callers at once: the room is spent at
    the estimate the moment the gate opens, so the next caller sees a window that is
    already smaller. `record` settles it with the exact figure, `release` gives it back.
    """

    id: int
    model: str
    phase: str | None


@dataclass(frozen=True)
class Limits:
    requests_minute: int
    tokens_minute: int
    requests_day: int
    tokens_day: int

    def ceiling(self, window: str, kind: str) -> int:
        return getattr(self, f"{kind}_{window}")


def limits_from_config() -> Limits:
    return Limits(
        requests_minute=config.CEREBRAS_MAX_REQUESTS_MINUTE,
        tokens_minute=config.CEREBRAS_MAX_TOKENS_MINUTE,
        requests_day=config.CEREBRAS_MAX_REQUESTS_DAY,
        tokens_day=config.CEREBRAS_MAX_TOKENS_DAY,
    )


def estimate_tokens(prompt: str) -> int:
    return int(len(prompt) / CHARS_PER_TOKEN) + _REQUEST_OVERHEAD_TOKENS


class Budget:
    def __init__(
        self,
        path: Path,
        limits: Callable[[], Limits] = limits_from_config,
        clock: Callable[[], float] = time.time,
    ):
        self._path = Path(path)
        # Beside the ledger and never the ledger itself: `write_json` replaces the file
        # through a `.tmp`, so a waiter holding the old inode would be guarding nothing.
        self._lock_path = self._path.with_name(self._path.name + ".lock")
        self._limits = limits
        self._clock = clock
        self._lock = threading.Lock()

    # THE GATE -----------------------------------------------------------------------------

    def delay(self, model: str, estimated_tokens: int) -> float:
        """Seconds to hold before this call may go out; raises when waiting is not the answer.

        A read, and only a read: it reserves nothing, so two callers asking at once both get
        an honest answer about a window neither has spent yet. `wait` is what books room.
        """
        with self._lock, self._flock():
            state = self._load()
        return self._compute(state, model, estimated_tokens)

    def _compute(self, state: dict, model: str, estimated_tokens: int) -> float:
        now = self._clock()
        limits = self._limits()
        calls = _calls(state, model)
        waits: list[float] = []

        for window, label, seconds in WINDOWS:
            for kind, need in (("requests", 1), ("tokens", max(estimated_tokens, 1))):
                # A call bigger than the WHOLE window can never fit, and waiting for it is
                # not slow, it is never: emptying the window restores the ceiling and the
                # ceiling is already too small. Reachable in practice — the model takes a
                # 131 072-token context while the free tier allows 30 000 tokens a minute,
                # so one large prompt is simply outside this budget. Without this guard
                # `_relief` finds no call to age out, reports relief «now», and the request
                # sails through to a 429 it will repeat for ever.
                ceiling = limits.ceiling(window, kind)
                if need > ceiling:
                    raise BudgetExhausted(
                        f"La llamada necesita {need} {'peticiones' if kind == 'requests' else 'tokens'} "
                        f"y el presupuesto de Cerebras {label} para '{model}' es de {ceiling} en total: "
                        "no cabe por más que se espere. Sube el límite en «Configuración» o "
                        "cambia de motor."
                    )
                remaining = self._remaining(state, model, calls, window, kind, seconds, now, limits)
                if remaining >= need:
                    continue
                until = _relief(state, model, calls, window, kind, seconds, now, need - remaining)
                wait = max(until - now, 0.0)
                if wait > config.CEREBRAS_MAX_WAIT_SECONDS:
                    raise BudgetExhausted(
                        f"El presupuesto de Cerebras {label} para '{model}' está agotado "
                        f"({kind == 'requests' and 'peticiones' or 'tokens'}): no se libera "
                        f"hasta dentro de {_human(wait)}. Cambia de motor, sube el límite en "
                        "«Configuración» o espera."
                    )
                waits.append(wait)

        return max(waits, default=0.0)

    def wait(self, model: str, estimated_tokens: int, phase: str | None = None) -> Claim:
        """Hold until the call fits, then BOOK its room and hand back the claim.

        It is a loop rather than one sleep because the room can be taken while we hold: with
        several jobs on the remote lane, whoever wakes first spends what came free and the
        rest go round again. Checking without booking is what would let all of them through
        at once — the defect this whole module exists to prevent, only with more callers.

        Cancellable throughout (`progress.checkpoint()` between one-second slices), and a
        cancellation gives the room back rather than leaving a claim nobody will settle.
        """
        with self._transaction() as state:
            claim = self._announce(state, model, phase)
        # Measured from the first attempt and not from each one, so a call cannot be held
        # for ever in short instalments while others keep taking the room in front of it.
        deadline = self._clock() + max(0.0, float(config.CEREBRAS_MAX_WAIT_SECONDS))
        announced = False
        try:
            while True:
                with self._transaction() as state:
                    held = self._compute(state, model, estimated_tokens)
                    if held <= 0:
                        self._book(state, claim, estimated_tokens)
                        return claim
                    if self._clock() + held > deadline:
                        raise BudgetExhausted(
                            f"El presupuesto de Cerebras para '{model}' no se libera a tiempo: "
                            f"harían falta {_human(held)} más y ya se ha agotado la espera "
                            f"máxima de {_human(float(config.CEREBRAS_MAX_WAIT_SECONDS))}. "
                            "Cambia de motor, sube el límite en «Configuración» o espera."
                        )
                    _waiting(state, claim, self._clock() + held)
                if not announced:
                    logger.info(
                        f"[cerebras] Budget spent for '{model}': waiting {held:.0f} s "
                        "for the window to roll"
                    )
                    progress.emit("cerebras.waiting", model=model, seconds=round(held))
                    announced = True
                self._hold(held)
        except BaseException:
            self.release(claim)
            raise

    def _hold(self, seconds: float) -> None:
        deadline = self._clock() + seconds
        while True:
            progress.checkpoint()
            left = deadline - self._clock()
            if left <= 0:
                return
            time.sleep(min(left, 1.0))

    # WHAT HAPPENED ------------------------------------------------------------------------

    def record(
        self,
        model: str,
        phase: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        headers,
        claim: Claim | None = None,
    ) -> None:
        """Charge the call what it actually cost, settling its claim if it had one.

        Without a claim it appends, which is what a call nobody booked looks like.
        """
        with self._transaction() as state:
            now = self._clock()
            bucket = _bucket(state, model)
            call = _booked(bucket, claim)
            if call is None:
                seq = int(state.get("seq", 0)) + 1
                state["seq"] = seq
                call = {"t": now, "n": seq}
                bucket["calls"].append(call)
            call.pop("hold", None)
            call["p"] = phase
            call["in"] = max(int(prompt_tokens), 0)
            call["out"] = max(int(completion_tokens), 0)
            # Against the claim's own sequence number, not the newest: a call answered while
            # a later one had already landed then subtracts that later one from the reading
            # too. It errs on the careful side, which is the only direction this file allows
            # a header to move what we believe is left.
            self._observe(bucket, headers, now, int(call["n"]))
            _land(state, claim)
            _prune(state, now)

    def release(self, claim: Claim | None) -> None:
        """Give back room that was booked and never spent. A settled claim is untouched."""
        if claim is None:
            return
        with self._transaction() as state:
            bucket = _bucket(state, claim.model)
            bucket["calls"] = [
                call
                for call in bucket["calls"]
                if not (call.get("n") == claim.id and call.get("hold"))
            ]
            _land(state, claim)

    def begin(self, model: str, phase: str | None, waiting: float | None = None) -> Claim:
        """Say a call is in flight without booking room for it. Returns its claim."""
        with self._transaction() as state:
            claim = self._announce(state, model, phase)
            if waiting:
                _waiting(state, claim, self._clock() + waiting)
            return claim

    def finish(self, claim: Claim | None = None) -> None:
        """Take a call out of the flight list. With no claim, take them all out."""
        with self._transaction() as state:
            if claim is None:
                state["inflight"] = []
            else:
                _land(state, claim)

    # Two halves of one booking. `_announce` only says somebody is trying, which is what the
    # panel draws while the throttle holds a call back; `_book` is what actually spends the
    # window, and it happens under the same transaction that found the room.
    def _announce(self, state: dict, model: str, phase: str | None) -> Claim:
        seq = int(state.get("seq", 0)) + 1
        state["seq"] = seq
        now = self._clock()
        _flying(state).append(
            {
                "id": seq,
                "model": model,
                "phase": phase,
                "since": now,
                "waiting_until": None,
            }
        )
        return Claim(id=seq, model=model, phase=phase)

    def _book(self, state: dict, claim: Claim, estimated_tokens: int) -> None:
        now = self._clock()
        bucket = _bucket(state, claim.model)
        bucket["calls"].append(
            {
                "t": now,
                "p": claim.phase,
                "in": max(int(estimated_tokens), 0),
                "out": 0,
                "n": claim.id,
                # When it was booked, so a claim left behind by a process that died stops
                # charging the budget on the same clock the flight list already uses.
                "hold": now,
            }
        )
        _waiting(state, claim, None)
        _prune(state, now)

    # WHAT THE PANEL READS -----------------------------------------------------------------

    def snapshot(self) -> dict:
        with self._lock, self._flock():
            state = self._load()
        now = self._clock()
        limits = self._limits()
        models = []
        for model in sorted(state.get("models", {})):
            calls = _calls(state, model)
            if not calls and not _bucket(state, model)["seen"]:
                continue
            models.append(
                {
                    "model": model,
                    "windows": {
                        window: self._meter(state, model, calls, window, seconds, now, limits)
                        for window, _, seconds in WINDOWS
                    },
                    "phases": _phases(calls, now),
                }
            )
        flying = _live_flights(state, now)
        # One entry is what the card draws, and a call being HELD is the one worth drawing:
        # «esperando presupuesto» is the state somebody can act on, and with several jobs on
        # the lane the oldest is not necessarily the one waiting. The count says the rest.
        return {
            "models": models,
            "inflight": flying[0] if flying else None,
            "inflight_count": len(flying),
        }

    def _meter(self, state, model, calls, window, seconds, now, limits) -> dict:
        inside = [call for call in calls if now - call["t"] < seconds]
        used = {
            "requests": len(inside),
            "tokens": sum(call["in"] + call["out"] for call in inside),
        }
        meter: dict = {"resets_in": _resets_in(inside, seconds, now)}
        for kind in ("requests", "tokens"):
            meter[f"{kind}_used"] = used[kind]
            meter[f"{kind}_limit"] = limits.ceiling(window, kind)
            meter[f"{kind}_remaining"] = max(
                self._remaining(state, model, calls, window, kind, seconds, now, limits), 0
            )
        return meter

    # THE ARITHMETIC -----------------------------------------------------------------------

    # Two readings of the same budget, and the smaller wins. The local one counts the exact
    # `usage` of every call still inside the window against the configured ceiling; the
    # server's says what IT will still answer, against a quota of its own that may be far
    # larger. Taking the minimum is what lets the second one matter without ever loosening
    # the first, and it is what makes a lagging token counter safe: a header can only ever
    # make us more careful.
    def _remaining(self, state, model, calls, window, kind, seconds, now, limits) -> int:
        ceiling = limits.ceiling(window, kind)
        inside = [call for call in calls if now - call["t"] < seconds]
        used = len(inside) if kind == "requests" else sum(c["in"] + c["out"] for c in inside)
        local = ceiling - used
        reported = _reported(state, model, calls, window, kind, seconds, now)
        return local if reported is None else min(local, reported)

    # What the server said, kept only to LOWER what we believe is left. It used to raise the
    # ceiling too, on the reading that a `remaining` above the settings could only mean a
    # bigger account — and that is what silently disabled the whole throttle: re-measured
    # 2026-08-29, `remaining-*` reports the MODEL's catalogue quota, so the first answer of
    # every installation ratcheted the ceilings to 499 req/min and 719 999 req/day and no
    # call was ever held again. The setting is the ceiling; a header never argues with it.
    def _observe(self, bucket: dict, headers, now: float, seq: int) -> None:
        for window, _, _seconds in WINDOWS:
            for kind in ("requests", "tokens"):
                raw = _header(headers, f"x-ratelimit-remaining-{kind}-{window}")
                if raw is None:
                    continue
                bucket["seen"][f"{kind}-{window}"] = [now, raw, seq]

    # THE FILE -----------------------------------------------------------------------------

    # One read-modify-write, exclusive against every other thread AND every other process.
    # The body raising means nothing is saved, which is what the gate wants: refusing a call
    # must not leave half a decision on disk.
    @contextmanager
    def _transaction(self):
        with self._lock, self._flock():
            state = self._load()
            yield state
            self._save(state)

    @contextmanager
    def _flock(self):
        if fcntl is None:
            yield
            return
        handle = None
        try:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(self._lock_path, "a+")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except OSError as e:
            # A ledger that cannot be locked is still a ledger worth keeping: degrade to the
            # process lock rather than refuse the call. Losing a race costs one miscounted
            # request; refusing here would take the engine down over a permissions problem.
            logger.warning(f"[cerebras] Could not lock the spending ledger: {e}")
            if handle is not None:
                handle.close()
            yield
            return
        try:
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def _load(self) -> dict:
        try:
            state = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return _empty()
        except (OSError, ValueError) as e:
            logger.warning(f"[cerebras] Could not read the spending ledger: {e}")
            return _empty()
        if not isinstance(state, dict) or not isinstance(state.get("models"), dict):
            return _empty()
        # A ledger written before the lane had room for two carries one flight or none.
        # Flights are transient, so the migration is to drop what does not fit the shape.
        if not isinstance(state.get("inflight"), list):
            state["inflight"] = []
        return state

    def _save(self, state: dict) -> None:
        try:
            write_json(self._path, state)
        except OSError as e:
            logger.warning(f"[cerebras] Could not save the spending ledger: {e}")


def _empty() -> dict:
    return {"models": {}, "inflight": [], "seq": 0}


def _flying(state: dict) -> list:
    flights = state.get("inflight")
    if not isinstance(flights, list):
        flights = []
        state["inflight"] = flights
    return flights


def _land(state: dict, claim: Claim | None) -> None:
    if claim is None:
        return
    state["inflight"] = [f for f in _flying(state) if f.get("id") != claim.id]


def _waiting(state: dict, claim: Claim, until: float | None) -> None:
    for flight in _flying(state):
        if flight.get("id") == claim.id:
            flight["waiting_until"] = until
            return


def _booked(bucket: dict, claim: Claim | None) -> dict | None:
    if claim is None:
        return None
    for call in bucket["calls"]:
        if call.get("n") == claim.id:
            return call
    return None


def _bucket(state: dict, model: str) -> dict:
    bucket = state.setdefault("models", {}).setdefault(model, {})
    bucket.setdefault("calls", [])
    bucket.setdefault("seen", {})
    bucket.pop("ceiling", None)
    return bucket


def _calls(state: dict, model: str) -> list[dict]:
    return list(state.get("models", {}).get(model, {}).get("calls", []))


# What the server said was left, brought forward to now by everything we have spent since it
# said it. Past the width of its own window the reading says nothing at all.
def _reported(state, model, calls, window, kind, seconds, now) -> int | None:
    seen = state.get("models", {}).get(model, {}).get("seen", {}).get(f"{kind}-{window}")
    if not seen:
        return None
    at, remaining, seq = seen[0], int(seen[1]), int(seen[2])
    if now - at >= seconds:
        return None
    after = [call for call in calls if call["n"] > seq]
    spent = len(after) if kind == "requests" else sum(c["in"] + c["out"] for c in after)
    return remaining - spent


# When enough capacity comes back: old calls age out of the window one by one, and a server
# reading stops binding once its own window has rolled. Both have to clear.
def _relief(state, model, calls, window, kind, seconds, now, deficit: int) -> float:
    times = []
    freed = 0
    for call in sorted((c for c in calls if now - c["t"] < seconds), key=lambda c: c["t"]):
        freed += 1 if kind == "requests" else call["in"] + call["out"]
        if freed >= deficit:
            times.append(call["t"] + seconds)
            break
    seen = state.get("models", {}).get(model, {}).get("seen", {}).get(f"{kind}-{window}")
    if seen and now - seen[0] < seconds:
        times.append(seen[0] + seconds)
    return max(times, default=now)


def _resets_in(inside: list[dict], seconds: float, now: float) -> float:
    if not inside:
        return 0.0
    return max(min(call["t"] for call in inside) + seconds - now, 0.0)


def _phases(calls: list[dict], now: float) -> list[dict]:
    rows: dict[str, dict] = {}
    for call in calls:
        if now - call["t"] >= 86_400.0:
            continue
        row = rows.setdefault(
            call["p"] or "sin fase",
            {"phase": call["p"] or "sin fase", "requests": 0, "prompt_tokens": 0, "completion_tokens": 0},
        )
        row["requests"] += 1
        row["prompt_tokens"] += call["in"]
        row["completion_tokens"] += call["out"]
    for row in rows.values():
        row["tokens"] = row["prompt_tokens"] + row["completion_tokens"]
    return sorted(rows.values(), key=lambda row: (-row["tokens"], row["phase"]))


# What is genuinely in flight, held ones first: a call the throttle is holding back is the
# one a person can do something about, and it is not always the oldest.
def _live_flights(state: dict, now: float) -> list[dict]:
    live = [
        {**flight, "elapsed": now - float(flight.get("since", now))}
        for flight in _flying(state)
        if now - float(flight.get("since", 0)) <= _INFLIGHT_STALE_SECONDS
    ]
    return sorted(
        live, key=lambda f: (f.get("waiting_until") is None, float(f.get("since", 0)))
    )


def _prune(state: dict, now: float) -> None:
    for bucket in state.get("models", {}).values():
        bucket["calls"] = [
            call
            for call in bucket["calls"]
            if now - call["t"] < 86_400.0
            # A booking whose process died never gets settled, and charging the day for it
            # would empty the budget over calls that never went out. Same clock as the
            # flight list, for the same reason.
            and not (call.get("hold") and now - float(call["hold"]) > _INFLIGHT_STALE_SECONDS)
        ]
    state["inflight"] = [
        flight
        for flight in _flying(state)
        if now - float(flight.get("since", 0)) <= _INFLIGHT_STALE_SECONDS
    ]


def _header(headers, name: str) -> int | None:
    try:
        raw = headers.get(name)
    except AttributeError:
        return None
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def _human(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5_400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3_600:.1f} h"


# THE INSTALLATION'S OWN LEDGER ---------------------------------------------------------------

# Global rather than per workspace, because the account is: two instances sharing a key
# share its budget, and a ledger per workspace would let each of them spend the whole thing.
_shared: Budget | None = None


def shared() -> Budget:
    global _shared
    if _shared is None:
        from .paths import PROJECT_ROOT

        _shared = Budget(PROJECT_ROOT / ".cerebras_budget.json")
    return _shared


# Point the ledger somewhere else, which the test suite does for every test: the engine
# tests answer a simulated transport, and without this they charged six phantom requests to
# the installation's real budget — a panel reporting spending that never happened.
def use(path: Path | None) -> None:
    global _shared
    _shared = None if path is None else Budget(path)
