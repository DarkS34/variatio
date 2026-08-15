"""Structured progress reporting and cooperative cancellation for the pipeline.

The core does not depend on a host: with no emitter installed every call here is
a no-op, so the CLI behaves exactly as it did before. A host (the FastAPI job
runner, or the bridge that runs `build` in a subprocess) installs an emitter with
`set_emitter` and starts receiving events.

The emitter lives in a ContextVar, so a worker thread that installs one does not
leak it into the threads serving HTTP requests.
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
    def emit(self, kind: str, payload: dict) -> None: ...

    def should_cancel(self) -> bool: ...


_emitter: contextvars.ContextVar["Emitter | None"] = contextvars.ContextVar(
    "variant_generator_emitter", default=None
)


# INSTALLATION ------------------------------------------------------------------------------------


def set_emitter(emitter: "Emitter | None") -> contextvars.Token:
    return _emitter.set(emitter)


def current_emitter() -> "Emitter | None":
    """Whoever is listening right now, so a caller can wrap it instead of replacing it."""
    return _emitter.get()


def reset_emitter(token: contextvars.Token) -> None:
    _emitter.reset(token)


@contextmanager
def emitting(emitter: "Emitter | None"):
    token = set_emitter(emitter)
    try:
        yield
    finally:
        reset_emitter(token)


# EMISSION ----------------------------------------------------------------------------------------


def emit(kind: str, **payload) -> None:
    emitter = _emitter.get()
    if emitter is not None:
        emitter.emit(kind, payload)


def should_cancel() -> bool:
    emitter = _emitter.get()
    return bool(emitter is not None and emitter.should_cancel())


def checkpoint() -> None:
    """Cooperative cancellation point: cheap to call, raises only when asked to stop."""
    if should_cancel():
        raise Cancelled("cancelled by the user")


class _StepHandle:
    __slots__ = ("id", "total", "current")

    def __init__(self, step_id: str, total: int | None):
        self.id = step_id
        self.total = total
        self.current = 0

    def tick(self, current: int | None = None, detail: str | None = None) -> None:
        self.current = self.current + 1 if current is None else current
        emit("step.progress", id=self.id, current=self.current, total=self.total, detail=detail)

    def total_is(self, total: int | None) -> None:
        """Late-bound total, for steps whose size is only known after some work."""
        self.total = total
        emit("step.total", id=self.id, total=total)


@contextmanager
def step(step_id: str, label: str, total: int | None = None):
    started = time.perf_counter()
    emit("step.started", id=step_id, label=label, total=total)
    handle = _StepHandle(step_id, total)
    try:
        yield handle
    except Cancelled:
        _finish(step_id, "cancelled", started)
        raise
    except BaseException as exc:  # noqa: BLE001 - re-raised right after reporting
        _finish(step_id, "failed", started, error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        _finish(step_id, "ok", started)


def _finish(step_id: str, status: str, started: float, error: str | None = None) -> None:
    emit(
        "step.finished",
        id=step_id,
        status=status,
        ms=round((time.perf_counter() - started) * 1000),
        error=error,
    )


def tick(step_id: str, current: int, total: int | None = None, detail: str | None = None) -> None:
    emit("step.progress", id=step_id, current=current, total=total, detail=detail)


# OVERALL PROGRESS --------------------------------------------------------------------------------

# Steps say *what* is running; they cannot say how much of the whole is left, because a
# build's phases cost wildly different amounts of time. A phase plan declares those costs
# once and turns the run into a single honest 0-100 bar.


class _Overall:
    __slots__ = ("_labels", "_spans", "_total", "_key")

    def __init__(self, plan: tuple[tuple[str, str, int], ...]):
        self._labels = {key: label for key, label, _ in plan}
        self._spans: dict[str, tuple[int, int]] = {}
        base = 0
        for key, _, weight in plan:
            self._spans[key] = (base, weight)
            base += weight
        self._total = base or 1
        self._key: str | None = None

    def phase(self, key: str, detail: str | None = None) -> None:
        self._key = key
        self.at(0.0, detail)

    def at(self, fraction: float, detail: str | None = None) -> None:
        if self._key is None:
            return
        base, weight = self._spans[self._key]
        done = base + weight * min(max(fraction, 0.0), 1.0)
        emit(
            "build.progress",
            percent=round(done * 100 / self._total),
            label=self._labels[self._key],
            detail=detail,
        )

    def finish(self) -> None:
        emit("build.progress", percent=100, label=None, detail=None)


_overall: contextvars.ContextVar["_Overall | None"] = contextvars.ContextVar(
    "variant_generator_overall", default=None
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


def token_sink(stream: str) -> Callable[[str, str], None] | None:
    """A per-token callback, or None when nobody is listening.

    Returning None lets callers fall back to the plain non-streaming request, which
    is what the CLI wants: no emitter, no streaming overhead, identical behaviour.
    """
    if _emitter.get() is None:
        return None

    def sink(text: str, channel: str) -> None:
        emit("token", stream=stream, text=text, channel=channel)

    return sink
