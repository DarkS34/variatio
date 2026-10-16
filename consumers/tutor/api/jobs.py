"""The tutor's two jobs: answering one turn, and drafting the subject's criteria.

Registered on `server.jobs.handlers.HANDLERS` by `consumers.tutor.api.install`, not declared there:
the queue is the installation's and the jobs are the tutor's. Both go through the queue for the
reason every model call does — the idle unloader reads the queue's clock, and a call outside
it would have the GPU released under it.

WHAT A TURN'S JOB SAYS IN PUBLIC IS NOTHING (`server.conversations.jobs`, shared with the free
chat): the job names the conversation and the turn and carries no text either way. The
student's message is read from the author's own file, and the reply is written back to it,
where only the author's routes read it — and so is the title the first substantive reply
brings, written in the same write as that reply. While the turn runs, only its steps reach
the stream.
"""

from loguru import logger

from server.conversations.jobs import QuietEmitter, release
from server import deps, installation, storage
from server.jobs.catalogue import Job
from server.jobs.handlers import context_for
from server.jobs.runner import JobControl
from variatio import entrypoints
from variatio.core import progress

from .. import ATTEMPT, EXERCISE, SOLUTION, THEORY
from .. import config as tutor_config
from .. import criteria as criteria_store
from .. import paths
from .. import prompts as tutor_prompts_pkg
from ..criteria_builder import build_criteria
from ..passages import cut_corpus, index_for
from ..title import name_conversation
from ..turn import run_turn
from . import store

TURN = "tutor_turn"
CRITERIA = "tutor_criteria"

# The kinds of reply that work on the subject, after which a conversation gets its title.
_TITLED_BY = (THEORY, EXERCISE, ATTEMPT, SOLUTION)


def handle_turn(job: Job, control: JobControl) -> dict:
    """Answer the student turn `job.params["turn"]` of one of the job author's conversations.

    The record is read twice, both times under the conversation's lock: at the start, for
    the message and the history, and again before the reply is appended, because the file
    is the one truth. The first read waits on the lock for a reason of its own — the route
    that queued this job holds it until `pending` is written, and a free lane starts the job
    before that, which read a record that did not yet name it.
    """
    ws = installation.workspace_for(job.workspace)
    conversation_id = str(job.params.get("conversation") or "")
    turn = int(job.params.get("turn", -1))
    if job.user_id is None:
        raise ValueError("Un turno del tutor no tiene autor.")
    with store.lock_for(ws, job.user_id, conversation_id):
        record = store.get(ws, job.user_id, conversation_id)
    if record is None or (record.get("pending") or {}).get("job_id") != job.id:
        raise ValueError("Esa conversación ya no espera este turno.")

    quiet = progress.set_emitter(QuietEmitter(control))
    try:
        deps.require_inference()
        context = context_for(job)
        tutor_prompts = tutor_prompts_pkg.of(context.language)
        sources = entrypoints.load_concept_sources(ws)
        criteria = criteria_store.load(
            ws, context.knowledge_graph, tutor_prompts.DEFAULT_ADMINISTRATIVE_REPLY
        )
        index = index_for(ws, sources, tutor_config.PASSAGE_CHARS)
        opened = record.get("opened_from") or {}
        result = run_turn(
            context,
            sources=sources,
            criteria=criteria,
            index=index,
            message=str(record["turns"][turn]["text"]),
            history=[
                {"role": t.get("role"), "text": t.get("text")} for t in record["turns"][:turn]
            ],
            state=record.get("state") or {},
            given_focus=list(opened.get("concepts") or []) or None,
            chosen=record["turns"][turn].get("concept") or None,
        )
        title = None
        if not record.get("titled") and result.kind in _TITLED_BY:
            asked = record["turns"][: turn + 1]
            title = name_conversation(
                [str(t.get("text") or "") for t in asked if t.get("role") == store.STUDENT],
                list(result.state.get("focus") or []),
                model=tutor_config.CLASSIFY_MODEL,
                tutor_prompts=tutor_prompts,
                prompts=context.prompts,
            )
    except progress.Cancelled:
        release(store.STORE, ws, job, conversation_id, turn, "cancelled")
        raise
    except Exception as exc:
        release(store.STORE, ws, job, conversation_id, turn, "failed")
        logger.warning(f"[tutor] El turno no se pudo responder: {exc}")
        raise
    finally:
        progress.reset_emitter(quiet)

    with store.lock_for(ws, job.user_id, conversation_id):
        fresh = store.get(ws, job.user_id, conversation_id)
        if fresh is None:
            logger.info("[tutor] La conversación se borró mientras se respondía; la respuesta se descarta")
            return {"conversation": conversation_id, "turn": turn}
        store.append_tutor(fresh, result.text, result.record())
        fresh["state"] = result.state
        if title:
            fresh["title"], fresh["titled"] = title, True
        fresh["pending"] = None
        store.write(ws, job.user_id, fresh)
    return {"conversation": conversation_id, "turn": turn + 1}


def handle_criteria(job: Job, control: JobControl) -> dict:
    """Draft the subject's criteria and write them as the draft, retiring a curated copy.

    A rebuild is asked for to REPLACE what is in force, so the teacher's curated file goes
    to the history — never deleted — and the new draft becomes what the tutor reads; the
    screen says so before the button is pressed. This is the contract the graph and the
    profile keep (`approvals.retire_curated`).
    """
    deps.require_inference()
    ws = installation.workspace_for(job.workspace)
    context = context_for(job)
    tutor_prompts = tutor_prompts_pkg.of(context.language)
    sources = entrypoints.load_concept_sources(ws)
    drafted = build_criteria(context, sources, cut_corpus(ws, sources, tutor_config.PASSAGE_CHARS))
    clean, warnings = criteria_store.normalize(
        drafted, context.knowledge_graph, tutor_prompts.DEFAULT_ADMINISTRATIVE_REPLY
    )
    for warning in warnings:
        logger.warning(f"[tutor] {warning}")
    storage.write_json(paths.criteria_draft_path(ws), clean, ws=ws, artifact=paths.CRITERIA_STEM)

    curated = paths.criteria_path(ws)
    if curated.is_file():
        storage.backup(ws, curated, paths.CRITERIA_STEM)
        curated.unlink()
        logger.info("[tutor] Los criterios corregidos pasan al historial; el borrador nuevo es el que vale")
    return {
        "general": len(clean["general"]),
        "units": sum(len(listed) for listed in clean["units"].values()),
        "forbidden_terms": len(clean["forbidden_terms"]),
    }
