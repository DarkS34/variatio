"""The `evaluate` job, and the one filter that keeps the run drawer from breaking the blind.

Registered on `server.jobs.handlers.HANDLERS` by `study.api.install`, not declared there:
the queue is the installation's and the job is the study's.
"""

from loguru import logger

from server import deps
from server.db import repository, session_scope
from server.jobs.handlers import context_for
from server.jobs.models import Job
from server.jobs.runner import JobControl
from variant_generator.core import progress

from .. import ARMS
from .. import run as study_run
from ..arms import rag as rag_arm
from . import store as evaluation_store


# WHAT THE EVALUATION IS ALLOWED TO SAY WHILE IT RUNS -------------------------------------------
#
# The run drawer is global and always visible, so without a filter the system gives away
# its own blinding: `VariantGenerator` emits `prompt` and `few_shot` unasked, the RAG arm
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


# WHO HAS TO JUDGE WHAT THIS PRODUCES ----------------------------------------------------
#
# A comparison ordered from the administration panel is STOCK: three items nobody has been
# handed yet, waiting for somebody to be judged competent for them. Recording it under
# whoever pressed the button put it in that person's own «Mis sesiones» and let them answer,
# unassigned, what they had prepared for somebody else — and since no answer ever rewrites
# `user_id`, the judgement would have been filed under that name too.
#
# So stock has no evaluator, and `store.assign` is the only thing that gives a set one.
def evaluator_of(job: Job) -> int | None:
    return None if job.params.get("stock") else job.user_id


def handle_evaluate(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = context_for(job)
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
        session = study_run.evaluate(
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
        evaluation_store.save(db_session, workspace.id, evaluator_of(job), session)

    produced = sum(1 for result in session.arms.values() if result.status == "ok")
    logger.success(
        f"Sesión {session.id}: {produced}/{len(ARMS)} propuestas con ítem válido"
    )
    # Deliberately WITHOUT the items: `job.result` travels over the WebSocket to every
    # client and stays in the event buffer. The items are read from
    # `GET /api/evaluation/{id}`, which knows what it may show and what it may not.
    return {"session_id": session.id, "arms": len(ARMS), "produced": produced}
