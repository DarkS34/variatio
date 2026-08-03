"""The warm pipeline context, built once and reused.

Building it embeds ~150 concept descriptions and the whole bank; doing that per
request would make the app unusable. It is deliberately *only* touched from the job
worker — REST handlers read artifacts straight off disk, so a slow context never
blocks the UI. Any write to an artifact invalidates it, and the next job rebuilds.
"""

import threading

from loguru import logger

from variant_generator import inference, stages
from variant_generator.stages import PipelineContext

_context: PipelineContext | None = None
_lock = threading.RLock()
_invalid_reason: str | None = None


def require_inference() -> None:
    if not inference.is_available():
        raise RuntimeError(
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'. "
            "Arranca Ollama antes de lanzar un trabajo."
        )


def get_context() -> PipelineContext:
    global _context, _invalid_reason
    with _lock:
        if _context is None:
            require_inference()
            if _invalid_reason:
                logger.info(f"Rebuilding pipeline context ({_invalid_reason})")
            _context = stages.initialize(tag=False)
            _invalid_reason = None
        return _context


def reload_context() -> PipelineContext:
    invalidate("reindexado solicitado")
    return get_context()


def invalidate(reason: str) -> None:
    global _context, _invalid_reason
    with _lock:
        if _context is not None:
            logger.info(f"Pipeline context invalidated: {reason}")
        _context = None
        _invalid_reason = reason


def peek() -> PipelineContext | None:
    with _lock:
        return _context


def is_ready() -> bool:
    return peek() is not None
