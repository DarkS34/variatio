"""What is left of Cerebras' rate limits, and the throttle that keeps us inside them.

Measured against the real API on 2026-08-26, with `gemma-4-31b` and `gpt-oss-120b`:

- Every response carries `x-ratelimit-{limit,remaining}-{requests,tokens}-{minute,hour,day}`
  and **no `reset` header at all**, so the window has to be reconstructed from our own call
  timestamps. That is what this module is: a rolling ledger.
- The `limit-*` headers report the MODEL's published quota (gemma: 500 req/min, 250 000
  uncached tok/min; gpt-oss: 1 000 and 500 000) and not the account's. The account's real
  ceiling shows up only in `remaining-*`, which on the free tier sits two to three orders of
  magnitude lower: 5 req/min, 30 000 tok/min, 2 400 req/day, 1 000 000 tok/day. So the
  ceilings here are settings, seeded with those measured numbers, and `limit-*` is ignored.
- The buckets are **per model**: a call to gpt-oss left `remaining-requests-day` at 2399 and
  the next call to gemma reported 2399 as well, each against its own 2 400.
- The request counters are exact; the token counters lag. A 74-token call and a 20-token
  call each moved `remaining-tokens-day` by exactly 6. So `usage` — which is exact and
  arrives with the answer — is what this ledger counts, and a header may only ever LOWER
  what we believe is left, never raise it.

The ledger is a file because builds run in `server.jobs.build_worker`, a separate process,
and they are precisely what empties a daily budget. Read-modify-write races are not guarded
against beyond a process-local lock: the job queue is one deep, so two processes never make
calls at the same time. An entry point that talks to Cerebras outside the queue breaks that.
"""

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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
        self._limits = limits
        self._clock = clock
        self._lock = threading.Lock()

    # THE GATE -----------------------------------------------------------------------------

    def delay(self, model: str, estimated_tokens: int) -> float:
        """Seconds to hold before this call may go out; raises when waiting is not the answer."""
        with self._lock:
            state = self._load()
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
                ceiling = _ceiling(state, model, window, kind, limits)
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

    def wait(self, model: str, estimated_tokens: int, phase: str | None = None) -> float:
        """Hold until the call fits, staying cancellable and saying so on the panel."""
        held = self.delay(model, estimated_tokens)
        if held <= 0:
            return 0.0
        logger.info(
            f"[cerebras] Presupuesto agotado para '{model}': se espera {held:.0f} s "
            "a que ruede la ventana"
        )
        self.begin(model, phase, waiting=held)
        progress.emit("cerebras.waiting", model=model, seconds=round(held))
        deadline = self._clock() + held
        while True:
            progress.checkpoint()
            left = deadline - self._clock()
            if left <= 0:
                return held
            time.sleep(min(left, 1.0))

    # WHAT HAPPENED ------------------------------------------------------------------------

    def record(
        self,
        model: str,
        phase: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        headers,
    ) -> None:
        with self._lock:
            state = self._load()
            now = self._clock()
            bucket = _bucket(state, model)
            seq = int(state.get("seq", 0)) + 1
            state["seq"] = seq
            bucket["calls"].append(
                {
                    "t": now,
                    "p": phase,
                    "in": max(int(prompt_tokens), 0),
                    "out": max(int(completion_tokens), 0),
                    "n": seq,
                }
            )
            self._observe(bucket, headers, now, seq)
            _prune(state, now)
            self._save(state)

    def begin(self, model: str, phase: str | None, waiting: float | None = None) -> None:
        with self._lock:
            state = self._load()
            now = self._clock()
            state["inflight"] = {
                "model": model,
                "phase": phase,
                "since": now,
                "waiting_until": now + waiting if waiting else None,
            }
            self._save(state)

    def finish(self) -> None:
        with self._lock:
            state = self._load()
            state["inflight"] = None
            self._save(state)

    # WHAT THE PANEL READS -----------------------------------------------------------------

    def snapshot(self) -> dict:
        with self._lock:
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
        return {"models": models, "inflight": _inflight(state, now)}

    def _meter(self, state, model, calls, window, seconds, now, limits) -> dict:
        inside = [call for call in calls if now - call["t"] < seconds]
        used = {
            "requests": len(inside),
            "tokens": sum(call["in"] + call["out"] for call in inside),
        }
        meter: dict = {"resets_in": _resets_in(inside, seconds, now)}
        for kind in ("requests", "tokens"):
            meter[f"{kind}_used"] = used[kind]
            meter[f"{kind}_limit"] = _ceiling(state, model, window, kind, limits)
            meter[f"{kind}_remaining"] = max(
                self._remaining(state, model, calls, window, kind, seconds, now, limits), 0
            )
        return meter

    # THE ARITHMETIC -----------------------------------------------------------------------

    # Two readings of the same budget, and the smaller wins. The local one counts the exact
    # `usage` of every call still inside the window; the server's is the truth about an
    # account whose real ceiling we never see directly. Taking the minimum is what makes a
    # lagging token counter safe: it can only ever make us more careful.
    def _remaining(self, state, model, calls, window, kind, seconds, now, limits) -> int:
        ceiling = _ceiling(state, model, window, kind, limits)
        inside = [call for call in calls if now - call["t"] < seconds]
        used = len(inside) if kind == "requests" else sum(c["in"] + c["out"] for c in inside)
        local = ceiling - used
        reported = _reported(state, model, calls, window, kind, seconds, now)
        return local if reported is None else min(local, reported)

    def _observe(self, bucket: dict, headers, now: float, seq: int) -> None:
        for window, _, _seconds in WINDOWS:
            for kind in ("requests", "tokens"):
                raw = _header(headers, f"x-ratelimit-remaining-{kind}-{window}")
                if raw is None:
                    continue
                bucket["seen"][f"{kind}-{window}"] = [now, raw, seq]
                # A remaining above what we think the ceiling is means the account is
                # bigger than the settings claim — a paid tier, or a raised quota. The
                # meter's denominator follows it up; the gate never needs to be told.
                key = f"{kind}-{window}"
                if raw > int(bucket["ceiling"].get(key, 0)):
                    bucket["ceiling"][key] = raw

    # THE FILE -----------------------------------------------------------------------------

    def _load(self) -> dict:
        try:
            state = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return _empty()
        except (OSError, ValueError) as e:
            logger.warning(f"[cerebras] No se pudo leer el registro de consumo: {e}")
            return _empty()
        if not isinstance(state, dict) or not isinstance(state.get("models"), dict):
            return _empty()
        return state

    def _save(self, state: dict) -> None:
        try:
            write_json(self._path, state)
        except OSError as e:
            logger.warning(f"[cerebras] No se pudo guardar el registro de consumo: {e}")


def _empty() -> dict:
    return {"models": {}, "inflight": None, "seq": 0}


def _bucket(state: dict, model: str) -> dict:
    bucket = state.setdefault("models", {}).setdefault(model, {})
    bucket.setdefault("calls", [])
    bucket.setdefault("seen", {})
    bucket.setdefault("ceiling", {})
    return bucket


def _calls(state: dict, model: str) -> list[dict]:
    return list(state.get("models", {}).get(model, {}).get("calls", []))


def _ceiling(state, model, window, kind, limits: Limits) -> int:
    learned = state.get("models", {}).get(model, {}).get("ceiling", {}).get(f"{kind}-{window}", 0)
    return max(limits.ceiling(window, kind), int(learned))


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


def _inflight(state: dict, now: float) -> dict | None:
    flying = state.get("inflight")
    if not flying:
        return None
    if now - float(flying.get("since", 0)) > _INFLIGHT_STALE_SECONDS:
        return None
    return {**flying, "elapsed": now - float(flying.get("since", now))}


def _prune(state: dict, now: float) -> None:
    for bucket in state.get("models", {}).values():
        bucket["calls"] = [call for call in bucket["calls"] if now - call["t"] < 86_400.0]


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
