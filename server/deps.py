"""The warm pipeline contexts, built once per workspace and reused.

Building one embeds ~150 concept descriptions and the whole bank; doing that per request
would make the app unusable. They are deliberately *only* touched from the job worker —
REST handlers read artifacts straight off disk, so a slow context never blocks the UI.
Any write to an artifact invalidates that workspace's context, and the next job rebuilds.

Since phase 3 this is a registry keyed by slug rather than one global, because with two
instances in one process a single slot meant one workspace's concept index answering the
other's queries. What bounds it is not memory — the two `.npz` of a real instance add up
to 3.3 MB and the vectors are already float32 — but the fact that rebuilding one costs
minutes, so keeping a handful warm is free and evicting eagerly is not.

Since the remote lane got a capacity, two jobs of the SAME workspace can run at once, and
both read this one context. Two things make that safe and both are load-bearing now rather
than incidentally true: `_lock` is held across `stages.initialize`, so the second job waits
for the build instead of starting a second one, and the components a context holds
(`Embedder`, `ConceptTagger`, `VariantGenerator`) assign no instance state after their
constructor — the only thing a run writes into them is the embedder's in-process memo,
where a race costs a repeated embedding and nothing else. A component that starts keeping
per-run state on `self` breaks this, and the lane is where it would show.
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
    if not inference.is_available():
        raise RuntimeError(
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'. "
            "Arranca Ollama antes de lanzar un trabajo."
        )


def get_context(ws: Workspace) -> PipelineContext:
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
    invalidate(ws.slug, "reindexado solicitado")
    return get_context(ws)


def invalidate(slug: str, reason: str) -> None:
    with _lock:
        if _contexts.pop(slug, None) is not None:
            logger.info(f"Contexto de «{slug}» invalidado: {reason}")
        _invalid_reasons[slug] = reason


def invalidate_all(reason: str) -> int:
    with _lock:
        slugs = list(_contexts)
        for slug in slugs:
            _contexts.pop(slug, None)
            _invalid_reasons[slug] = reason
        if slugs:
            logger.info(f"[contextos] {len(slugs)} contexto(s) invalidado(s): {reason}")
        return len(slugs)


def peek(slug: str) -> PipelineContext | None:
    with _lock:
        return _contexts.get(slug)


def is_ready(slug: str) -> bool:
    return peek(slug) is not None


def warm_slugs() -> list[str]:
    with _lock:
        return list(_contexts)


# Least recently *used*, not least recently built: a workspace somebody is working in
# keeps its turn on every job it runs.
def _evict() -> None:
    while len(_contexts) > MAX_CONTEXTS:
        slug, _ = _contexts.popitem(last=False)
        logger.info(f"Contexto de «{slug}» descargado: el registro está lleno")
