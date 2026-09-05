"""The `evaluate` job, and the one filter that keeps the run drawer from breaking the blind.

Registered on `server.jobs.handlers.HANDLERS` by `evaluation.api.install`, not declared there:
the queue is the installation's and the job is the evaluation's.
"""

from loguru import logger

from server import deps
from server.db import repository, session_scope
from server.jobs.handlers import context_for
from server.jobs.catalogue import Job
from server.jobs.runner import JobControl
from variatio.core import progress

from .. import ARMS
from .. import run as evaluation_run
from ..arms import rag as rag_arm
from . import store as evaluation_store


# WHAT THE EVALUATION IS ALLOWED TO SAY WHILE IT RUNS -------------------------------------------

_EVAL_STEP_PREFIX = "eval."


class _BlindEmitter:
    """Let through only this stage's own heartbeat, and drop everything the arms emit.

    The run drawer is global and always visible, so without this the system gives away its
    own blinding: the generator emits `prompt` and `few_shot` unasked and the token stream
    reads like a signature. A whitelist rather than a blacklist, because ANY inner step
    identifies its arm — only the system's has a guardrail step, only the RAG arm an index
    one — and the ids that survive count work done without ever naming a position.
    """

    def __init__(self, inner):
        """Wrap the emitter the job publishes through."""
        self._inner = inner

    def emit(self, kind: str, payload: dict) -> None:
        """Forward the event only when it is one of this stage's own `eval.` steps."""
        if kind.startswith("step.") and str(payload.get("id", "")).startswith(_EVAL_STEP_PREFIX):
            self._inner.emit(kind, payload)

    def should_cancel(self) -> bool:
        """Defer the cancellation question to the emitter underneath."""
        return self._inner.should_cancel()


# WHO HAS TO JUDGE WHAT THIS PRODUCES ----------------------------------------------------


def evaluator_of(job: Job) -> int | None:
    """Return who owns the session this job produces, which for stock is nobody.

    A comparison ordered from the administration panel waits for somebody to be judged
    competent for it, and `store.assign` is the only thing that gives a set an evaluator.
    Recording stock under whoever pressed the button would let them answer, unassigned,
    what they had prepared for somebody else.
    """
    return None if job.params.get("stock") else job.user_id


def handle_evaluate(job: Job, control: JobControl) -> dict:
    """Run one blind comparison and save it, with the run drawer muted throughout."""
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
    )

    # Warmed BEFORE the blind section: built inside the arm, this one-off cost would land in
    # the RAG baseline's `elapsed_ms` and its step would be swallowed by the filter. Both
    # slots, and by WORKSPACE: the arm stopped retrieving over the bank on 2026-09-04 and
    # this call was left naming the old one-index signature, so every evaluation job died
    # here with a TypeError before a single proposal was written.
    rag_arm.warm(context.workspace)

    # `_BlindEmitter` is the whole of the blinding now. The loguru mirror it also had to
    # silence published «few-shot seleccionado» on the bus, which gave away which proposal
    # was the system's; since 2026-08-31 that mirror writes to `logs/<slug>/jobs.log` and
    # reaches no screen, so there is nothing left to mute — and the file keeps everything,
    # which is what one wants when a session has to be explained afterwards.
    with progress.emitting(_BlindEmitter(control)):
        session = evaluation_run.evaluate(
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
                f"La asignatura '{job.workspace}' ya no está en la base de datos: "
                "la sesión de evaluación no se puede guardar."
            )
        evaluation_store.save(db_session, workspace.id, evaluator_of(job), session)

    produced = sum(1 for result in session.arms.values() if result.status == "ok")
    logger.success(
        f"Sesión {session.id}: {produced}/{len(ARMS)} propuestas con ítem válido"
    )
    # Deliberately WITHOUT the items: `job.result` travels over the WebSocket to every
    # client and stays in the event buffer. They are read from `GET /api/evaluation/{id}`,
    # which knows what it may show and what it may not.
    return {"session_id": session.id, "arms": len(ARMS), "produced": produced}
