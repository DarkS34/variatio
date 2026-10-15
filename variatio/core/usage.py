"""What the model calls of one piece of work cost, in tokens, phase by phase.

A meter is opened around a piece of work (`metering()`), and every call the engine boundary
makes while one is open adds its tokens to it: what the prompt cost and what the answer cost,
under the phase that made the call — `progress.current_activity()`, the very name the Cerebras
ledger charges a remote call to — with the engine and the model that answered. Ollama says
both counts on the last chunk of a stream (`prompt_eval_count`, `eval_count`); Cerebras in its
`usage`. A stream abandoned before its end (a stop, a loop) says nothing, and is counted as a
call with no tokens: what is not known is not guessed.

Meters nest: a call counts on every meter open around it, so a job's meter holds everything
its turn did while the turn keeps its own figure for its record.

Each call counts on the thread that made it (a context variable): a piece of work that hands
calls to other threads opens a meter on each, or loses them.
"""

import contextvars
import threading
from contextlib import contextmanager

from . import progress

# What a meter is told when a call made under no phase: still counted, under this name.
NO_PHASE = "-"

_meters: contextvars.ContextVar[tuple["Meter", ...]] = contextvars.ContextVar("usage_meters", default=())


class Meter:
    """The tokens of one piece of work, by phase, as calls report them."""

    def __init__(self) -> None:
        """Start empty."""
        self._lock = threading.Lock()
        self._phases: dict[tuple[str, str, str], dict] = {}

    def add(self, phase: str | None, engine: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        """Count one call."""
        key = (phase or NO_PHASE, engine, model)
        with self._lock:
            row = self._phases.setdefault(key, {"calls": 0, "in": 0, "out": 0})
            row["calls"] += 1
            row["in"] += max(int(prompt_tokens or 0), 0)
            row["out"] += max(int(completion_tokens or 0), 0)

    def summary(self) -> dict:
        """Return the totals and one row per phase, engine and model, the costliest first."""
        with self._lock:
            rows = [
                {"phase": phase, "engine": engine, "model": model, **counts}
                for (phase, engine, model), counts in self._phases.items()
            ]
        rows.sort(key=lambda row: (-(row["in"] + row["out"]), row["phase"]))
        return {
            "calls": sum(row["calls"] for row in rows),
            "in": sum(row["in"] for row in rows),
            "out": sum(row["out"] for row in rows),
            "phases": rows,
        }

    def merge(self, summary: object) -> None:
        """Add a summary another process measured (a build's worker) to this meter."""
        for row in clean(summary).get("phases", []):
            key = (row["phase"], row["engine"], row["model"])
            with self._lock:
                held = self._phases.setdefault(key, {"calls": 0, "in": 0, "out": 0})
                for field in ("calls", "in", "out"):
                    held[field] += row[field]

    def __bool__(self) -> bool:
        """A meter is true once something was counted on it."""
        with self._lock:
            return bool(self._phases)


@contextmanager
def metering():
    """Open a meter for the work inside the block, on this thread, and hand it over."""
    meter = Meter()
    token = _meters.set((*_meters.get(), meter))
    try:
        yield meter
    finally:
        _meters.reset(token)


def record(engine: str, model: str, prompt_tokens: int | None, completion_tokens: int | None) -> None:
    """Count one model call on every meter open on this thread; nothing when none is."""
    meters = _meters.get()
    if not meters:
        return
    phase = progress.current_activity()
    for meter in meters:
        meter.add(phase, engine, model, prompt_tokens or 0, completion_tokens or 0)


def add(summary: object) -> None:
    """Count a summary another process measured on every meter open on this thread."""
    for meter in _meters.get():
        meter.merge(summary)


def clean(summary: object) -> dict:
    """Return a summary read from outside (a worker's pipe) with only well-formed rows kept."""
    if not isinstance(summary, dict):
        return {"calls": 0, "in": 0, "out": 0, "phases": []}
    rows = []
    for row in summary.get("phases") or []:
        if not isinstance(row, dict):
            continue
        try:
            rows.append(
                {
                    "phase": str(row.get("phase") or NO_PHASE)[:80],
                    "engine": str(row.get("engine") or "")[:40],
                    "model": str(row.get("model") or "")[:120],
                    "calls": max(int(row.get("calls") or 0), 0),
                    "in": max(int(row.get("in") or 0), 0),
                    "out": max(int(row.get("out") or 0), 0),
                }
            )
        except (TypeError, ValueError):
            continue
    return {
        "calls": sum(row["calls"] for row in rows),
        "in": sum(row["in"] for row in rows),
        "out": sum(row["out"] for row in rows),
        "phases": rows,
    }
