"""What each job kind actually does. One place, so the runner stays generic."""

from loguru import logger

from variant_generator import config, progress, stages
from variant_generator.concept_tagger import ConceptTagger

from .. import deps, review
from .build_process import run_build
from .models import Job
from .runner import JobControl


def _build(artifact: str):
    def handler(job: Job, control: JobControl) -> dict:
        return run_build(artifact, control)

    return handler


# Building the context embeds every concept description and the whole bank. It is
# minutes of silence the first time, so it gets its own step and says what it costs.
def _context(reload: bool = False):
    if deps.is_ready() and not reload:
        logger.info("Índices ya calientes en memoria: se reutilizan")
        return deps.get_context()

    label = (
        "Reconstruyendo el contexto: instancia + índices"
        if reload
        else "Preparando el contexto: cargando la instancia e indexando"
    )
    with progress.step("context", label):
        logger.info(
            "Cargando perfil, grafo y banco, y calculando los embeddings que falten "
            f"con '{config.EMBEDDING_LLM}' (se reutiliza la caché de cache/embeddings/)"
        )
        context = deps.reload_context() if reload else deps.get_context()
    logger.success(
        f"Contexto listo: {len(context.embedder.concepts_index)} concepto(s) indexado(s) "
        f"y {len(context.exemplars_bank)} ítem(s) del banco"
    )
    return context


def handle_describe_concepts(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    concepts = job.params.get("concepts")
    overwrite = bool(job.params.get("overwrite"))
    logger.info(
        f"Escribiendo descripciones con '{config.DESCRIPTION_GENERATION_LLM}': "
        + (
            f"{len(concepts)} concepto(s) seleccionado(s)"
            if concepts
            else "todos los conceptos etiquetables"
        )
        + (" (se reescriben las existentes)" if overwrite else " (solo los que no la tienen)")
    )
    descriptions = stages.describe_concepts(concepts=concepts, overwrite=overwrite)
    # New prose means new embeddings; the cached context would keep matching the old.
    deps.invalidate("descripciones de conceptos regeneradas")
    logger.success(
        f"{len(descriptions)} descripción(es) disponibles. El índice se recalculará en el "
        "próximo trabajo que lo necesite."
    )
    return {"described": len(descriptions)}


def handle_index(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = _context(reload=True)
    return {
        "concepts": len(context.embedder.concepts_index),
        "items": len(context.exemplars_bank),
    }


def handle_tag(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = _context()
    ids = job.params.get("ids") or None
    pending = ids if ids is not None else ConceptTagger.pending_ids(context.exemplars_bank)
    logger.info(
        f"A etiquetar: {len(pending)} de {len(context.exemplars_bank)} ítem(s). "
        f"Cada uno recupera candidatos del índice y los verifica con '{config.CONCEPT_TAGGER_LLM}' "
        f"(umbral {config.EMBEDDER_SIMILARITY_THRESHOLD}, "
        f"{config.TAGGER_TOP_K_CANDIDATES} candidatos como máximo)."
    )
    bank = stages.tag_bank(context, ids=ids)
    untagged = [i for i, item in bank.items() if not item.get("concepts")]
    logger.success(
        f"Banco etiquetado: {len(bank) - len(untagged)} con conceptos, {len(untagged)} sin ellos "
        "(los que quedan sin etiquetar se reintentan en la próxima pasada)."
    )
    return {
        "items": len(bank),
        "tagged": len(bank) - len(untagged),
        "untagged": len(untagged),
    }


def handle_generate(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = _context()
    params = job.params
    n = int(params.get("n") or 1)
    concepts = params.get("concepts") or None
    fixed = params.get("fixed") or None
    curriculum = params.get("curriculum") or None

    logger.info(
        f"Generando {n} ítem(s) con '{config.CONTENT_GENERATION_LLM}' sobre "
        + (", ".join(concepts) if concepts else "los conceptos más frecuentes del banco")
    )
    if fixed:
        logger.info("Campos fijados: " + ", ".join(f"{k}={v}" for k, v in fixed.items()))
    if curriculum:
        logger.info(
            f"Currículo activo con {len(curriculum)} concepto(s): el ítem no podrá exigir nada fuera de ahí"
        )

    results = stages.generate(context, concepts=concepts, n=n, fixed=fixed, curriculum=curriculum)
    if len(results) < n:
        logger.warning(
            f"Se pidieron {n} ítem(s) y se validaron {len(results)}: el resto no pasó el esquema"
        )
    else:
        logger.success(f"{len(results)} ítem(s) generados y validados contra el perfil")
    return {
        "requested": n,
        "produced": len(results),
        "items": [
            {"item": r.item.model_dump(mode="json"), "thinking": r.thinking} for r in results
        ],
    }


HANDLERS = {
    "build_profile": _build(review.CONTENT_PROFILE),
    "build_kg": _build(review.KNOWLEDGE_GRAPH),
    "build_bank": _build(review.EXEMPLARS_BANK),
    "describe_concepts": handle_describe_concepts,
    "index": handle_index,
    "tag": handle_tag,
    "generate": handle_generate,
}
