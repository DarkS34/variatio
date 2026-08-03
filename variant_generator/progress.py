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
    "checkpoint",
    "emit",
    "model_loading",
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


def model_loading(model: str, role: str) -> None:
    """Swapping models on a single GPU costs real seconds; make it a visible step."""
    emit("model.loading", model=model, role=role)


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
