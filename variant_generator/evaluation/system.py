"""Arm 3 — this pipeline, exactly as it ships.

One call to `context.generator.generate(...)`: no new parameter, no `if` inside
`ContentGenerator`. If the evaluation needed to modify the generator, it would already
be measuring something other than the system.

The prompt, the exemplars it chose and the raw answer are not returned by `generate()`,
so they are read off the event stream it already emits — observing, not adapting.
"""

import time

from loguru import logger

from .. import config, inference, progress
from . import FAILED, OK, ArmResult, Commission


class _Capture:
    """A tee on the emitter: records what the run says, forwards it to whoever listens."""

    def __init__(self, inner):
        self._inner = inner
        self.prompt = ""
        self.exemplar_ids: list[str] = []
        self.answer: list[str] = []
        self.thinking: list[str] = []

    def emit(self, kind: str, payload: dict) -> None:
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
        return bool(self._inner is not None and self._inner.should_cancel())

    @property
    def raw(self) -> str:
        return "".join(self.answer) or "".join(self.thinking)


def run(commission: Commission, context) -> ArmResult:
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
            )
        except progress.Cancelled:
            raise
        except Exception as e:  # noqa: BLE001 - a failed arm is a datum, not a crash
            error = f"{type(e).__name__}: {e}"
            logger.warning(f"System arm failed: {error}")

    item = results[0].item.model_dump(mode="json") if results else None
    if item is None and error is None:
        error = "el ítem generado no pasó la validación contra el perfil de contenido"

    return ArmResult(
        arm="system",
        status=OK if item is not None else FAILED,
        item=item,
        raw_response=capture.raw,
        prompt=capture.prompt,
        model=config.CONTENT_GENERATION_LLM,
        provider=inference.engine_name(),
        exemplar_ids=capture.exemplar_ids,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        error=error,
    )
