"""The warm pipeline contexts, an LRU registry keyed by workspace slug.

Building one embeds ~150 concept descriptions and the whole bank, so they are touched only
from the job worker — REST handlers read artifacts straight off disk and a slow context
never blocks the UI. Any write to an artifact invalidates that workspace's context and the
next job rebuilds it. What bounds `MAX_CONTEXTS` is not memory but that rebuilding one
costs minutes.

Two jobs of the same workspace can run at once on different lanes and share one context.
`_lock` is held across `stages.initialize` so the second waits instead of starting a second
build, and the components a context holds (`Embedder`, `ConceptTagger`,
`VariantGenerator`) assign no instance state after their constructor. A component that
starts keeping per-run state on `self` breaks that.
"""

import threading
from collections import OrderedDict

from loguru import logger

from variatio import stages
from variatio.core import inference
from variatio.core.workspace import Workspace
from variatio.stages import PipelineContext

MAX_CONTEXTS = 8

_contexts: "OrderedDict[str, PipelineContext]" = OrderedDict()
_invalid_reasons: dict[str, str] = {}
_lock = threading.RLock()


def require_inference() -> None:
    """Raise unless the inference engine answers, before a job pays for a build."""
    if not inference.is_available():
        raise RuntimeError(
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'. "
            "Arranca Ollama antes de lanzar un trabajo."
        )


def get_context(ws: Workspace) -> PipelineContext:
    """Return the workspace's warm context, building it under the lock if there is none."""
    with _lock:
        existing = _contexts.get(ws.slug)
        if existing is not None:
            _contexts.move_to_end(ws.slug)
            return existing

        require_inference()
        reason = _invalid_reasons.pop(ws.slug, None)
        if reason:
            logger.info(f"Reconstruyendo el contexto de «{ws.slug}»: {reason}")

        context = stages.initialize(tag=False, ws=ws)
        _contexts[ws.slug] = context
        _evict()
        return context


def reload_context(ws: Workspace) -> PipelineContext:
    """Drop the workspace's context and build it again."""
    invalidate(ws.slug, "reindexado solicitado")
    return get_context(ws)


def invalidate(slug: str, reason: str) -> None:
    """Evict one workspace's context, recording why for the next build's log line."""
    with _lock:
        if _contexts.pop(slug, None) is not None:
            logger.info(f"Contexto de «{slug}» invalidado: {reason}")
        _invalid_reasons[slug] = reason


def invalidate_all(reason: str) -> int:
    """Evict every warm context and return how many there were."""
    with _lock:
        slugs = list(_contexts)
        for slug in slugs:
            _contexts.pop(slug, None)
            _invalid_reasons[slug] = reason
        if slugs:
            logger.info(f"[contextos] {len(slugs)} contexto(s) invalidado(s): {reason}")
        return len(slugs)


def peek(slug: str) -> PipelineContext | None:
    """Return a workspace's context if it is already warm, without building one."""
    with _lock:
        return _contexts.get(slug)


def is_ready(slug: str) -> bool:
    """Report whether a workspace's context is warm."""
    return peek(slug) is not None


def warm_slugs() -> list[str]:
    """List the workspaces holding a warm context."""
    with _lock:
        return list(_contexts)


def _evict() -> None:
    """Drop the least recently USED contexts down to `MAX_CONTEXTS`.

    Used and not built, so a workspace somebody is working in keeps its turn on every job
    it runs.
    """
    while len(_contexts) > MAX_CONTEXTS:
        slug, _ = _contexts.popitem(last=False)
        logger.info(f"Contexto de «{slug}» descargado: el registro está lleno")
