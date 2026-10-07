"""The warm pipeline contexts, an LRU registry keyed by workspace slug.

Building one embeds ~150 concept descriptions and the whole bank, so they are touched only
from the job worker — REST handlers read artifacts straight off disk and a slow context
never blocks the UI. Any write to an artifact invalidates that workspace's context and the
next job rebuilds it. What bounds `MAX_CONTEXTS` is not memory but that rebuilding one
costs minutes.

Two jobs of the same workspace can run at once on different lanes and share one context.
Each workspace has its own lock, held across `entrypoints.initialize`, so the second job waits
instead of starting a second build — and a job of ANOTHER workspace never waits for it: one
lock for every context made a class's tutor turns wait while a teacher's subject warmed up.
`_lock` itself only guards the registry's dicts and is never held across a build. The
components a context holds (`Embedder`, `ConceptTagger`, `VariantGenerator`) assign no
instance state after their constructor. A component that starts keeping per-run state on
`self` breaks that.

An invalidation that lands while its workspace is being built does not wait for the build:
it bumps the workspace's generation, and the build that started under the old one hands its
context to the job that asked and keeps it out of the registry.
"""

import threading
from collections import OrderedDict

from loguru import logger

from variatio import entrypoints
from variatio.core import inference
from variatio.core.workspace import Workspace
from variatio.entrypoints import RuntimeContext

MAX_CONTEXTS = 8

_contexts: "OrderedDict[str, RuntimeContext]" = OrderedDict()
_invalid_reasons: dict[str, str] = {}
_generations: dict[str, int] = {}
_building: dict[str, threading.Lock] = {}
_lock = threading.RLock()


def reload_context(ws: Workspace) -> RuntimeContext:
    """Drop the workspace's context and build it again."""
    invalidate(ws.slug, "reindexado solicitado")
    return get_context(ws)


def invalidate(slug: str, reason: str) -> None:
    """Evict one workspace's context, recording why for the next build's log line."""
    with _lock:
        if _contexts.pop(slug, None) is not None:
            logger.info(f"Contexto de «{slug}» invalidado: {reason}")
        _invalid_reasons[slug] = reason
        _generations[slug] = _generations.get(slug, 0) + 1


def get_context(ws: Workspace) -> RuntimeContext:
    """Return the workspace's warm context, building it under its own lock if there is none."""
    warm = _warm(ws.slug)
    if warm is not None:
        return warm
    with _lock:
        building = _building.setdefault(ws.slug, threading.Lock())
    with building:
        # Whoever held the lock before us may have built it.
        warm = _warm(ws.slug)
        if warm is not None:
            return warm
        require_inference()
        with _lock:
            reason = _invalid_reasons.pop(ws.slug, None)
            generation = _generations.get(ws.slug, 0)
        if reason:
            logger.info(f"Reconstruyendo el contexto de «{ws.slug}»: {reason}")

        context = entrypoints.initialize(tag=False, ws=ws)
        with _lock:
            if _generations.get(ws.slug, 0) == generation:
                _contexts[ws.slug] = context
                _evict()
        return context


def _warm(slug: str) -> RuntimeContext | None:
    """Return a workspace's warm context, marking it the most recently used, or None."""
    with _lock:
        existing = _contexts.get(slug)
        if existing is not None:
            _contexts.move_to_end(slug)
        return existing


def require_inference() -> None:
    """Raise unless the inference engine answers, before a job pays for a build."""
    if not inference.is_available():
        raise RuntimeError(
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'. "
            "Arranca Ollama antes de lanzar un trabajo."
        )


def _evict() -> None:
    """Drop the least recently USED contexts down to `MAX_CONTEXTS`.

    Used and not built, so a workspace somebody is working in keeps its turn on every job
    it runs.
    """
    while len(_contexts) > MAX_CONTEXTS:
        slug, _ = _contexts.popitem(last=False)
        logger.info(f"Contexto de «{slug}» descargado: el registro está lleno")


def invalidate_all(reason: str) -> int:
    """Evict every warm context and return how many there were."""
    with _lock:
        slugs = list(_contexts)
        for slug in slugs:
            _contexts.pop(slug, None)
            _invalid_reasons[slug] = reason
        for slug in set(_generations) | set(_building):
            _generations[slug] = _generations.get(slug, 0) + 1
        if slugs:
            logger.info(f"[contextos] {len(slugs)} contexto(s) invalidado(s): {reason}")
        return len(slugs)


def is_ready(slug: str) -> bool:
    """Report whether a workspace's context is warm."""
    return peek(slug) is not None


def peek(slug: str) -> RuntimeContext | None:
    """Return a workspace's context if it is already warm, without building one."""
    with _lock:
        return _contexts.get(slug)


def warm_slugs() -> list[str]:
    """List the workspaces holding a warm context."""
    with _lock:
        return list(_contexts)
