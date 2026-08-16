"""What each job kind actually does. One place, so the runner stays generic.

Every handler resolves its paths from `job.workspace` and nothing else. That is the rule
phase 3 rests on: the runner is one queue for the whole installation, so a handler that
read a process-wide workspace would write one person's build into another's directory.
"""

from loguru import logger

from variant_generator import config, progress, stages
from variant_generator.concept_tagger import ConceptTagger
from variant_generator.evaluation import ARMS
from variant_generator.evaluation import rag as rag_arm
from variant_generator.workspace import Workspace

from .. import deps, evaluation_store, review, settings
from ..db import repository, session_scope, study
from .build_process import run_build
from .models import Job
from .runner import JobControl


def _workspace(job: Job) -> Workspace:
    return settings.workspace_for(job.workspace)


def _build(artifact: str):
    def handler(job: Job, control: JobControl) -> dict:
        return run_build(artifact, control)

    return handler


# Building the context embeds every concept description and the whole bank. It is
# minutes of silence the first time, so it gets its own step and says what it costs.
def _context(job: Job, reload: bool = False):
    ws = _workspace(job)
    if deps.is_ready(ws.slug) and not reload:
        logger.info("Índices ya calientes en memoria: se reutilizan")
        return deps.get_context(ws)

    label = (
        "Reconstruyendo el contexto: instancia + índices"
        if reload
        else "Preparando el contexto: cargando la instancia e indexando"
    )
    with progress.step("context", label):
        logger.info(
            "Cargando perfil, grafo y banco, y calculando los embeddings que falten "
            f"con '{config.EMBEDDING_LLM}' (se reutiliza la caché de {ws.cache_dir.name}/embeddings/)"
        )
        context = deps.reload_context(ws) if reload else deps.get_context(ws)
    logger.success(
        f"Contexto listo: {len(context.embedder.concepts_index)} concepto(s) indexado(s) "
        f"y {len(context.exemplars_bank)} ítem(s) del banco"
    )
    return context


def handle_describe_concepts(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    ws = _workspace(job)
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
    descriptions = stages.describe_concepts(concepts=concepts, overwrite=overwrite, ws=ws)
    # New prose means new embeddings; the cached context would keep matching the old.
    deps.invalidate(ws.slug, "descripciones de conceptos regeneradas")
    logger.success(
        f"{len(descriptions)} descripción(es) disponibles. El índice se recalculará en el "
        "próximo trabajo que lo necesite."
    )
    return {"described": len(descriptions)}


def handle_index(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = _context(job, reload=True)
    return {
        "concepts": len(context.embedder.concepts_index),
        "items": len(context.exemplars_bank),
    }


def handle_tag(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = _context(job)
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
    context = _context(job)
    params = job.params
    n = int(params.get("n") or 1)
    concepts = params.get("concepts") or None
    item_type = params.get("item_type") or None
    fixed = params.get("fixed") or None
    curriculum = params.get("curriculum") or None
    instructions = params.get("instructions") or None
    # Absent means "as it always was": every caller that predates the switch reasons.
    think = bool(params.get("think", True))

    resolved_type = context.exemplars_profile.item_type(item_type)
    logger.info(
        f"Generando {n} ítem(s) de tipo «{resolved_type.label}» con "
        f"'{config.CONTENT_GENERATION_LLM}' sobre "
        + (", ".join(concepts) if concepts else "los conceptos más frecuentes del banco")
    )
    if fixed:
        logger.info("Campos fijados: " + ", ".join(f"{k}={v}" for k, v in fixed.items()))
    if curriculum:
        logger.info(
            f"Currículo activo con {len(curriculum)} concepto(s): el ítem no podrá exigir nada fuera de ahí"
        )
    if instructions:
        logger.info(f"Instrucciones adicionales: «{instructions}»")
    logger.info(
        "El modelo razonará antes de escribir cada ítem: tarda más, pero delibera sobre el objetivo"
        if think
        else "Sin razonamiento previo: el modelo responde directamente y va más rápido"
    )

    results = stages.generate(
        context,
        concepts=concepts,
        item_type=resolved_type.key,
        n=n,
        fixed=fixed,
        curriculum=curriculum,
        instructions=instructions,
        think=think,
    )
    if len(results) < n:
        logger.warning(
            f"Se pidieron {n} ítem(s) y se validaron {len(results)}: el resto no pasó el esquema"
        )
    else:
        logger.success(f"{len(results)} ítem(s) generados y validados contra el perfil")

    items = [
        {
            "item": r.item.model_dump(mode="json"),
            "item_type": r.item_type,
            "thinking": r.thinking,
        }
        for r in results
    ]
    saved = _remember(job, items, resolved_type.key)
    return {
        "requested": n,
        "produced": len(results),
        "item_type": resolved_type.key,
        "saved": saved,
        "items": items,
    }


# Persisting the variants is deliberately best-effort: a database that is briefly away
# must not turn a minute of GPU into a failed job, because the items are already in the
# job result and on screen. What is lost is the history, and the log says so.
def _remember(job: Job, items: list[dict], item_type: str) -> int:
    if not items:
        return 0
    params = job.params
    try:
        with session_scope() as session:
            workspace = repository.get_workspace(session, job.workspace)
            if workspace is None:
                return 0
            for entry in items:
                study.save_generation(
                    session,
                    workspace_id=workspace.id,
                    user_id=job.user_id,
                    job_id=job.id,
                    item_type=entry.get("item_type") or item_type,
                    item=entry["item"],
                    concepts=params.get("concepts") or [],
                    curriculum=params.get("curriculum") or [],
                    fixed=params.get("fixed") or {},
                    instructions=params.get("instructions"),
                    think=bool(params.get("think", True)),
                    thinking=entry.get("thinking"),
                )
    except Exception as exc:  # noqa: BLE001 - the run succeeded; only its record did not
        logger.warning(f"No se pudieron guardar las variantes en la base de datos: {exc}")
        return 0
    logger.info(f"{len(items)} variante(s) guardadas en el historial")
    return len(items)


# WHAT THE EVALUATION IS ALLOWED TO SAY WHILE IT RUNS -------------------------------------------
#
# The run drawer is global and always visible, so without a filter the system gives away
# its own blinding: `ContentGenerator` emits `prompt` and `few_shot` unasked, the RAG arm
# announces its retrieval, and the token stream reads like a signature.
#
# A whitelist rather than a blacklist, because ANY inner step identifies its arm — only
# the system's arm has a guardrail step, only the RAG arm has an index step. What survives
# is the heartbeat this stage emits about itself, whose ids all start with `eval.` and
# which counts work done without ever naming a position.
_EVAL_STEP_PREFIX = "eval."


class _BlindEmitter:
    def __init__(self, inner):
        self._inner = inner

    def emit(self, kind: str, payload: dict) -> None:
        if kind.startswith("step.") and str(payload.get("id", "")).startswith(_EVAL_STEP_PREFIX):
            self._inner.emit(kind, payload)

    def should_cancel(self) -> bool:
        return self._inner.should_cancel()


def handle_evaluate(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = _context(job)
    params = job.params
    concepts = params.get("concepts") or []
    fixed = params.get("fixed") or None
    curriculum = params.get("curriculum") or None
    instructions = params.get("instructions") or None
    resolved_type = context.exemplars_profile.item_type(params.get("item_type") or None)

    logger.info(
        f"Comparación ciega de {len(ARMS)} propuestas de tipo «{resolved_type.label}» sobre "
        + (", ".join(concepts) if concepts else "ningún concepto")
    )
    logger.info(
        "Durante la comparación el registro y el progreso interno quedan ocultos: "
        "revelarían qué propuesta ha salido de qué arquitectura."
    )

    # Warmed BEFORE the blind section on purpose. Built inside the arm it would land in
    # that arm's `elapsed_ms` and make the RAG baseline look slow for a one-off cost, and
    # its step would be swallowed by the filter, leaving the screen silent while it runs.
    rag_arm.index_for(context).ensure()

    with control.muted_logs(), progress.emitting(_BlindEmitter(control)):
        session = stages.evaluate(
            context,
            concepts=concepts,
            item_type=resolved_type.key,
            fixed=fixed,
            curriculum=curriculum,
            instructions=instructions,
            seed=params.get("seed"),
            job_id=job.id,
        )

    with session_scope() as db_session:
        workspace = repository.get_workspace(db_session, job.workspace)
        if workspace is None:
            raise RuntimeError(
                f"El workspace '{job.workspace}' ya no está en la base de datos: "
                "la sesión de evaluación no se puede guardar."
            )
        evaluation_store.save(db_session, workspace.id, job.user_id, session)

    produced = sum(1 for result in session.arms.values() if result.status == "ok")
    logger.success(
        f"Sesión {session.id}: {produced} de {len(ARMS)} propuestas con ítem válido. "
        "Los orígenes se revelan al elegir."
    )
    # Deliberately WITHOUT the items: `job.result` travels over the WebSocket to every
    # client and stays in the event buffer. The items are read from
    # `GET /api/evaluation/{id}`, which knows what it may show and what it may not.
    return {"session_id": session.id, "arms": len(ARMS), "produced": produced}


HANDLERS = {
    "build_profile": _build(review.EXEMPLARS_PROFILE),
    "build_kg": _build(review.KNOWLEDGE_GRAPH),
    "build_bank": _build(review.EXEMPLARS_BANK),
    "describe_concepts": handle_describe_concepts,
    "index": handle_index,
    "tag": handle_tag,
    "generate": handle_generate,
    "evaluate": handle_evaluate,
}
