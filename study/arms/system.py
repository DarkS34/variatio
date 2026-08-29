"""Arm 3 — this pipeline, exactly as it ships.

One call to `context.generator.generate(...)`: no `if` inside `VariantGenerator`. If the
evaluation needed to modify the generator, it would already be measuring something other
than the system. `think` is not an exception to that — it is a parameter the Generate
screen offers to every user, and this arm merely forwards the value the session drew.

The prompt, the exemplars it chose and the raw answer are not returned by `generate()`,
so they are read off the event stream it already emits — observing, not adapting.
"""

import time

from loguru import logger

from variatio import config
from variatio.core import inference, progress

from .. import FAILED, OK, ArmResult, Commission


class _Capture:
    """A tee on the emitter: records what the run says, forwards it to whoever listens."""

    def __init__(self, inner):
        """Wrap the emitter the run is already publishing to, or nothing."""
        self._inner = inner
        self.prompt = ""
        self.exemplar_ids: list[str] = []
        self.answer: list[str] = []
        self.thinking: list[str] = []

    def emit(self, kind: str, payload: dict) -> None:
        """Keep the prompt, the exemplars and the token stream, then forward the event."""
        if kind == "prompt":
            self.prompt = payload.get("text") or self.prompt
        elif kind == "few_shot":
            self.exemplar_ids = list(payload.get("ids") or [])
        elif kind == "token":
            target = self.thinking if payload.get("channel") == "thinking" else self.answer
            target.append(payload.get("text") or "")
        if self._inner is not None:
            self._inner.emit(kind, payload)

    def should_cancel(self) -> bool:
        """Defer the cancellation question to whoever is listening underneath."""
        return bool(self._inner is not None and self._inner.should_cancel())

    @property
    def raw(self) -> str:
        """Return what the model wrote, falling back to the reasoning channel."""
        return "".join(self.answer) or "".join(self.thinking)


def run(commission: Commission, context) -> ArmResult:
    """Generate one item through the pipeline untouched, capturing what it emits."""
    started = time.perf_counter()
    capture = _Capture(progress.current_emitter())

    error: str | None = None
    results = []
    with progress.emitting(capture):
        try:
            results = context.generator.generate(
                concepts=commission.concepts,
                item_type=commission.item_type,
                n=1,
                fixed=commission.fixed or None,
                curriculum=commission.curriculum or None,
                instructions=commission.instructions or None,
                think=commission.think,
                check=True,
                ruling=commission.ruling,
            )
        except progress.Cancelled:
            raise
        except Exception as e:  # noqa: BLE001 - a failed arm is a datum, not a crash
            error = f"{type(e).__name__}: {e}"
            logger.warning(f"Falló la propuesta del sistema: {error}")

    item = results[0].item.model_dump(mode="json") if results else None
    if item is None and error is None:
        error = "el ítem generado no pasó la validación contra el perfil de ejemplares"

    return ArmResult(
        arm="system",
        status=OK if item is not None else FAILED,
        item=item,
        raw_response=capture.raw,
        prompt=capture.prompt,
        model=config.VARIANT_GENERATION_LLM,
        provider=inference.engine_name(),
        exemplar_ids=capture.exemplar_ids,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        error=error,
        checks=results[0].checks if results else None,
        retried=results[0].retried if results else 0,
    )
