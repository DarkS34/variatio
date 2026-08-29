"""Structured progress reporting and cooperative cancellation for the pipeline.

The core does not depend on a host: with no emitter installed every call here is a no-op,
so the CLI behaves as if none of it existed. A host — the FastAPI job runner, or the
bridge that runs `build` in a subprocess — installs an emitter with `set_emitter` and
starts receiving events.

The emitter lives in a ContextVar, so a worker thread that installs one does not leak it
into the threads serving HTTP requests.
"""

import contextvars
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Protocol

__all__ = [
    "Cancelled",
    "Emitter",
    "advance",
    "checkpoint",
    "current_activity",
    "current_emitter",
    "emit",
    "overall",
    "phase",
    "reset_emitter",
    "set_emitter",
    "should_cancel",
    "step",
    "tick",
    "token_sink",
]


class Cancelled(RuntimeError):
    """Raised at a cancellation checkpoint when the host asked to stop."""


class Emitter(Protocol):
    """What a host has to provide to receive events and to ask for a stop."""

    def emit(self, kind: str, payload: dict) -> None:
        """Deliver one event to the host."""
        ...

    def should_cancel(self) -> bool:
        """Whether the host has asked the running work to stop."""
        ...


_emitter: contextvars.ContextVar["Emitter | None"] = contextvars.ContextVar(
    "variatio_emitter", default=None
)


# INSTALLATION ------------------------------------------------------------------------------------


def set_emitter(emitter: "Emitter | None") -> contextvars.Token:
    """Install an emitter for this context; returns the token that undoes it."""
    return _emitter.set(emitter)


def current_emitter() -> "Emitter | None":
    """Whoever is listening right now, so a caller can wrap it instead of replacing it."""
    return _emitter.get()


def reset_emitter(token: contextvars.Token) -> None:
    """Undo the installation `token` came from."""
    _emitter.reset(token)


@contextmanager
def emitting(emitter: "Emitter | None"):
    """Install an emitter for the duration of the block."""
    token = set_emitter(emitter)
    try:
        yield
    finally:
        reset_emitter(token)


# EMISSION ----------------------------------------------------------------------------------------


def emit(kind: str, **payload) -> None:
    """Send one event; a no-op when nobody is listening."""
    emitter = _emitter.get()
    if emitter is not None:
        emitter.emit(kind, payload)


def should_cancel() -> bool:
    """Whether the host has asked to stop; False when nobody is listening."""
    emitter = _emitter.get()
    return bool(emitter is not None and emitter.should_cancel())


def checkpoint() -> None:
    """Cooperative cancellation point: cheap to call, raises only when asked to stop."""
    if should_cancel():
        raise Cancelled("cancelled by the user")


class _StepHandle:
    """The running step, handed to the block so it can report its own progress."""

    __slots__ = ("current", "id", "total")

    def __init__(self, step_id: str, total: int | None):
        """Start a step at zero, with the total its caller already knows."""
        self.id = step_id
        self.total = total
        self.current = 0

    def tick(self, current: int | None = None, detail: str | None = None) -> None:
        """Report one more unit done, or jump to `current`."""
        self.current = self.current + 1 if current is None else current
        emit("step.progress", id=self.id, current=self.current, total=self.total, detail=detail)

    def total_is(self, total: int | None) -> None:
        """Late-bound total, for steps whose size is only known after some work."""
        self.total = total
        emit("step.total", id=self.id, total=total)


_step: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "variatio_step", default=None
)


@contextmanager
def step(step_id: str, label: str, total: int | None = None):
    """Run a named step, reporting how it ended — ok, cancelled or failed — either way."""
    started = time.perf_counter()
    emit("step.started", id=step_id, label=label, total=total)
    handle = _StepHandle(step_id, total)
    token = _step.set(step_id)
    try:
        yield handle
    except Cancelled:
        _finish(step_id, "cancelled", started)
        raise
    except BaseException as exc:
        _finish(step_id, "failed", started, error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        _finish(step_id, "ok", started)
    finally:
        _step.reset(token)


def _finish(step_id: str, status: str, started: float, error: str | None = None) -> None:
    """Emit the closing event of a step, with how long it took."""
    emit(
        "step.finished",
        id=step_id,
        status=status,
        ms=round((time.perf_counter() - started) * 1000),
        error=error,
    )


def tick(step_id: str, current: int, total: int | None = None, detail: str | None = None) -> None:
    """Report progress of a step by id, for a caller holding no handle."""
    emit("step.progress", id=step_id, current=current, total=total, detail=detail)


# OVERALL PROGRESS --------------------------------------------------------------------------------


class _Overall:
    """A build's phase plan, as one honest 0-100 bar.

    Steps say *what* is running and cannot say how much of the whole is left, because a
    build's phases cost wildly different amounts of time. The plan declares those costs
    once, as weights, and every phase's progress is scaled into its own span.
    """

    __slots__ = ("_key", "_labels", "_spans", "_total")

    def __init__(self, plan: tuple[tuple[str, str, int], ...]):
        """Lay the plan's weights out as consecutive spans of the whole bar."""
        self._labels = {key: label for key, label, _ in plan}
        self._spans: dict[str, tuple[int, int]] = {}
        base = 0
        for key, _, weight in plan:
            self._spans[key] = (base, weight)
            base += weight
        self._total = base or 1
        self._key: str | None = None

    def phase(self, key: str, detail: str | None = None) -> None:
        """Enter a phase of the plan, at zero."""
        self._key = key
        self.at(0.0, detail)

    def at(self, fraction: float, detail: str | None = None) -> None:
        """Report how far into the current phase the work is, as a fraction of that phase.

        The phase key travels with the percentage: a host drawing the plan as segments has
        to know which one is running, and reading that back from the percentage guesses
        wrong exactly at the boundaries.
        """
        if self._key is None:
            return
        base, weight = self._spans[self._key]
        done = base + weight * min(max(fraction, 0.0), 1.0)
        emit(
            "build.progress",
            percent=round(done * 100 / self._total),
            key=self._key,
            label=self._labels[self._key],
            detail=detail,
        )

    def finish(self) -> None:
        """Close the bar at 100 %, naming no phase."""
        emit("build.progress", percent=100, key=None, label=None, detail=None)


_overall: contextvars.ContextVar["_Overall | None"] = contextvars.ContextVar(
    "variatio_overall", default=None
)


@contextmanager
def overall(plan: tuple[tuple[str, str, int], ...]):
    """Install a weighted `(key, label, weight)` phase plan for the duration of a build."""
    bar = _Overall(plan)
    token = _overall.set(bar)
    try:
        yield bar
        bar.finish()
    finally:
        _overall.reset(token)


def phase(key: str, detail: str | None = None) -> None:
    """Enter a phase of the installed plan; a no-op when the stage runs standalone."""
    bar = _overall.get()
    if bar is not None:
        bar.phase(key, detail)


def advance(fraction: float, detail: str | None = None) -> None:
    """How far along the current phase is, as a 0-1 fraction of that phase alone."""
    bar = _overall.get()
    if bar is not None:
        bar.at(fraction, detail)


def current_activity() -> str | None:
    """What is running, in the vocabulary the caller already has.

    A build's phase key while a plan is installed, the running step's id otherwise — which
    is what the tagger, the describer and the generator have. The Cerebras ledger reads it
    to attribute every remote call to a phase; outside both, `None` is an answer.
    """
    bar = _overall.get()
    if bar is not None and bar._key is not None:
        return bar._key
    return _step.get()


def token_sink(stream: str) -> Callable[[str, str], None] | None:
    """A per-token callback, or None when nobody is listening.

    Returning None lets callers fall back to the plain non-streaming request, which
    is what the CLI wants: no emitter, no streaming overhead, identical behaviour.
    """
    if _emitter.get() is None:
        return None

    def sink(text: str, channel: str) -> None:
        """Forward one token of `stream` to the host."""
        emit("token", stream=stream, text=text, channel=channel)

    return sink
