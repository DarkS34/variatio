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
from variant_generator.exemplars_profile import ExemplarsProfile
from variant_generator.knowledge_graph import KnowledgeGraph
from variant_generator.workspace import Workspace

from .. import deps, evaluation_store, review, settings, storage
from ..db import repository, session_scope, study
from ..editors import kg_edit
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
        logger.info("Índices ya calientes en memoria; se reutilizan")
        return deps.get_context(ws)

    label = (
        "Reconstruyendo el contexto: instancia + índices"
        if reload
        else "Preparando el contexto: cargando la instancia e indexando"
    )
    with progress.step("context", label):
        logger.info(f"Cargando la instancia e indexando con '{config.EMBEDDING_LLM}'")
        context = deps.reload_context(ws) if reload else deps.get_context(ws)
    logger.success(
        f"Contexto listo: {len(context.embedder.concepts_index)} concepto(s) indexado(s), "
        f"{len(context.exemplars_bank)} ítem(s) del banco"
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
        + (", reescribiendo las existentes" if overwrite else ", solo las que faltan")
    )
    descriptions = stages.describe_concepts(concepts=concepts, overwrite=overwrite, ws=ws)
    # New prose means new embeddings; the cached context would keep matching the old.
    deps.invalidate(ws.slug, "descripciones de conceptos regeneradas")
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
        f"A etiquetar: {len(pending)} de {len(context.exemplars_bank)} ítem(s), "
        f"verificados con '{config.CONCEPT_TAGGER_LLM}'"
    )
    bank = stages.tag_bank(context, ids=ids)
    untagged = [i for i, item in bank.items() if not item.get("concepts")]
    logger.success(
        f"Banco etiquetado: {len(bank) - len(untagged)} con conceptos, {len(untagged)} sin ellos"
    )
    return {
        "items": len(bank),
        "tagged": len(bank) - len(untagged),
        "untagged": len(untagged),
    }


def handle_review_taggability(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    ws = _workspace(job)

    profile_path = stages.exemplars_profile_path(ws)
    if profile_path is None:
        raise ValueError(
            "La etiquetabilidad se decide contra el perfil de ejemplares, y este "
            "workspace no lo tiene todavía: constrúyelo antes."
        )

    graph_path = stages.knowledge_graph_path(ws)
    if graph_path is None:
        raise ValueError("No hay grafo de conocimiento que revisar.")

    from variant_generator import taggability

    profile = ExemplarsProfile(profile_path)
    graph = KnowledgeGraph(graph_path)
    bank = storage.read_json(ws.exemplars_bank_path) or {}

    with progress.overall(taggability.BUILD_PHASES):
        progress.phase("taggable")
        non_taggable = taggability.review(graph, profile, bank)

    result = kg_edit.set_non_taggable(ws, non_taggable)
    return {"non_taggable": result["non_taggable"], "concepts": len(graph.all_concepts)}


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
    detail = []
    if fixed:
        detail.append("campos fijados " + ", ".join(f"{k}={v}" for k, v in fixed.items()))
    if curriculum:
        detail.append(f"currículo de {len(curriculum)} concepto(s)")
    if instructions:
        detail.append(f"instrucciones «{instructions}»")
    detail.append("con razonamiento" if think else "sin razonamiento")
    logger.info(
        f"Generando {n} ítem(s) de tipo «{resolved_type.label}» con "
        f"'{config.CONTENT_GENERATION_LLM}' sobre "
        + (", ".join(concepts) if concepts else "los conceptos más frecuentes del banco")
        + " — "
        + "; ".join(detail)
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
        logger.warning(f"{len(results)}/{n} ítem(s) validados; el resto no pasó el esquema")
    else:
        logger.success(f"{len(results)}/{n} ítem(s) generados y validados")

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
        + " — el registro interno queda oculto para no revelar el origen de cada una"
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
        f"Sesión {session.id}: {produced}/{len(ARMS)} propuestas con ítem válido"
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
    "review_taggability": handle_review_taggability,
    "generate": handle_generate,
    "evaluate": handle_evaluate,
}
