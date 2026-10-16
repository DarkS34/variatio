"""The free chat's one job: answering one turn.

Registered on `server.jobs.catalogue.HANDLERS` by `consumers.chat.api.install`. It goes through the
queue for the reason every model call does — the idle unloader reads the queue's clock — and
says nothing in public (`server.conversations.jobs`): it names the conversation and the turn,
reads the message from the author's own file and writes the reply back to it.

It needs no runtime context: the guardrail reads the workspace's prompt set, and the reply the
subject's description (`content_context`). So a chat turn never warms the embedder or the
graph of a subject.
"""

from loguru import logger

from server.conversations.jobs import QuietEmitter, release
from server.core import contexts, installation
from server.jobs.catalogue import Job
from server.jobs.runner import JobControl
from variatio import prompts as prompt_sets
from variatio.core import progress
from variatio.loaders import content_context, locale

from ..turn import run_turn
from .store import STORE

TURN = "chat_turn"


def handle_turn(job: Job, control: JobControl) -> dict:
    """Answer the student turn `job.params["turn"]` of one of the job author's conversations.

    The record is read twice, both times under the conversation's lock: at the start, for the
    message and the history, and again before the reply is appended, because the file is the
    one truth. The first read waits on the lock because the route that queued this job holds
    it until `pending` is written.
    """
    ws = installation.workspace_for(job.workspace)
    conversation_id = str(job.params.get("conversation") or "")
    turn = int(job.params.get("turn", -1))
    if job.user_id is None:
        raise ValueError("Un turno del chat no tiene autor.")
    with STORE.lock_for(ws, job.user_id, conversation_id):
        record = STORE.get(ws, job.user_id, conversation_id)
    if record is None or (record.get("pending") or {}).get("job_id") != job.id:
        raise ValueError("Esa conversación ya no espera este turno.")

    quiet = progress.set_emitter(QuietEmitter(control))
    try:
        contexts.require_inference()
        language = locale.prompt_language(ws)
        opened = record.get("opened_from") or {}
        result = run_turn(
            language=language,
            prompts=prompt_sets.of(language),
            subject=content_context.load_for(ws).prompt_block(),
            message=str(record["turns"][turn]["text"]),
            history=[{"role": t.get("role"), "text": t.get("text")} for t in record["turns"][:turn]],
            exercise=[tuple(pair) for pair in opened.get("exercise") or []] or None,
        )
    except progress.Cancelled:
        release(STORE, ws, job, conversation_id, turn, "cancelled")
        raise
    except Exception as exc:
        release(STORE, ws, job, conversation_id, turn, "failed")
        logger.warning(f"[chat] El turno no se pudo responder: {exc}")
        raise
    finally:
        progress.reset_emitter(quiet)

    with STORE.lock_for(ws, job.user_id, conversation_id):
        fresh = STORE.get(ws, job.user_id, conversation_id)
        if fresh is None:
            logger.info("[chat] La conversación se borró mientras se respondía; la respuesta se descarta")
            return {"conversation": conversation_id, "turn": turn}
        STORE.append_reply(fresh, result.text, result.record())
        fresh["pending"] = None
        STORE.write(ws, job.user_id, fresh)
    return {"conversation": conversation_id, "turn": turn + 1}
