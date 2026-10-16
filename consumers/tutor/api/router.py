"""The tutor's routes: a student's conversations, and the subject's criteria for its teachers.

Declares `auth.VIEW` for the whole router, because the tutor is for the students of the subject
(`viewer`); the criteria routes add `auth.EDIT`, because what the tutor demands of a subject is
a teacher's to decide. The account's own profile (`evaluator_profile`) is not read here: it
authorises nothing inside a subject, where the membership role is the one that counts.

EVERY CONVERSATION ROUTE IS SCOPED TO THE ACCOUNT THAT ASKS, exactly as the generated exercises
are: the author's directory is the only one read, and another account's conversation, another
workspace's and a malformed id all answer the same 404. The installation administrator reads
every account's, read-only, through its own panel (`consumers.tutor.api.admin`), never through
these.

A message is answered by a job of the queue, so it waits behind a build on the local lane like
any other model call. Three rules keep that queue from filling with one person's turns: one
reply at a time per conversation (409 while it is live), one per account in the workspace, and
the installation's daily limit per account (`tutor.daily_messages`, 429 when it is reached).

The whole router is also behind `auth.TUTOR`: the tutor is open to nobody, to every account or
to a list, as the administrator set it (`server/auth/features.py`).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server.conversations import routes as shared

from server import auth, singletons
from server import generations as generations_store
from server.editors import bank_edit
from server.jobs.catalogue import Job
from server.pipeline import approvals, storage
from server.routers.exercises import reader_of
from variatio import entrypoints
from variatio.core import inference
from variatio.loaders import locale
from variatio.loaders.knowledge_graph import KnowledgeGraph

from .. import config as tutor_config
from .. import criteria as criteria_store
from .. import paths
from .. import prompts as tutor_prompts_pkg
from . import jobs, store, usage

router = APIRouter(prefix="/api/tutor", tags=["tutor"], dependencies=[auth.VIEW, auth.TUTOR])

# The tutor as the routes every conversational function shares need it.
TUTOR = shared.Function(
    store=store.STORE,
    limit=usage.LIMIT,
    turn=jobs.TURN,
    busy="El tutor ya está contestando otra conversación tuya; espera a que termine.",
    daily=lambda: tutor_config.DAILY_MESSAGES,
    max_chars=lambda: tutor_config.MESSAGE_MAX_CHARS,
)


class MessageBody(BaseModel):
    """A student's message, with what it is about when the student said so.

    `generation_id` is the generated exercise a conversation is opened on, and `bank_id` the
    exercise of the bank (one this account may read, `/api/exercises`); `concept` the concept
    of the syllabus the student chose beside the box for this one message.
    """

    message: str
    generation_id: str | None = None
    bank_id: str | None = None
    concept: str | None = None


class CriteriaBody(BaseModel):
    """A teacher's whole criteria document, as the screen edits it."""

    criteria: dict


@router.get("")
def status(access: auth.Access = auth.VIEW) -> dict:
    """Answer whether the tutor can answer here, and the state of the subject's criteria."""
    data, origin = criteria_store.read(access.ws)
    job = _criteria_job(access.ws.slug)
    blocked = _chain_error(access)
    return {
        "ready": blocked is None,
        "blocked": blocked,
        "criteria": {
            "origin": origin,
            "built": (data or {}).get("built") if isinstance(data, dict) else None,
            "job": job.to_dict() if job else None,
        },
        "can_edit": access.role in ("editor", "owner"),
    }


@router.get("/conversations")
def conversations(access: auth.Access = auth.VIEW) -> dict:
    """Answer one's own conversations in this workspace, the most recently active first."""
    return {
        "conversations": [
            _row(_heal(access, record)) for record in store.list_for(access.ws, access.user.id)
        ]
    }


@router.post("/conversations", status_code=201)
def open_conversation(
    body: MessageBody, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Start a conversation with its first message and queue the tutor's reply."""
    message = _checked_message(body.message, access)
    concept = _checked_concept(body.concept, access)
    _admit(access, db)
    if body.generation_id and body.bank_id:
        raise HTTPException(422, "Una conversación se abre sobre un ejercicio, no sobre dos.")
    opened_from = None
    if body.generation_id:
        record = generations_store.get(access.ws, access.user.id, body.generation_id)
        if record is None:
            raise HTTPException(404, "Ese ejercicio no existe.")
        opened_from = {
            "kind": "generation",
            "generation_id": body.generation_id,
            "concepts": generations_store.concepts_of(record),
            "item_type": generations_store.item_type_of(record),
        }
    elif body.bank_id:
        opened_from = _opened_on_bank(body.bank_id, access, db)
    conversation = store.create(access.ws, access.user.id, message, opened_from, concept=concept)
    with store.lock_for(access.ws, access.user.id, conversation["id"]):
        job = _queue_turn(access, db, conversation, 0)
    return {"conversation": _detail(conversation), "job": job.to_dict()}


def _opened_on_bank(item_id: str, access: auth.Access, db: DbSession) -> dict:
    """Name the exercise of the bank a conversation opens on, if this account may read it.

    Its content key goes with its id, so a reading per exercise survives a re-extraction
    that renumbers the bank. Refused like a missing one when it is hidden from this account.
    """
    group_id, every_group = reader_of(db, access)
    try:
        item = bank_edit.readable(access.ws, item_id, group_id, every_group)
    except bank_edit.BankError:
        item = None
    if item is None:
        raise HTTPException(404, "Ese ejercicio no existe.")
    primary = item.get("primary_concept")
    concepts = [c for c in [primary, *item["concepts"]] if c]
    return {
        "kind": "bank",
        "bank_id": item_id,
        "key": item["key"],
        "concepts": list(dict.fromkeys(concepts)),
        "item_type": item["item_type"],
    }


@router.get("/criteria", dependencies=[auth.EDIT])
def criteria(access: auth.Access = auth.EDIT) -> dict:
    """Answer the criteria in force, cleaned against the graph, with the subject's units."""
    tutor_prompts = tutor_prompts_pkg.of(_language(access))
    data, origin = criteria_store.read(access.ws)
    graph = _graph(access)
    document, warnings = criteria_store.normalize(
        data or criteria_store.empty(tutor_prompts.DEFAULT_ADMINISTRATIVE_REPLY),
        graph,
        tutor_prompts.DEFAULT_ADMINISTRATIVE_REPLY,
    )
    return {
        "origin": origin,
        "criteria": document,
        "warnings": warnings,
        "units": [
            {"name": unit, "concepts": list(graph.concepts_by_domains.get(unit, []))}
            for unit in getattr(graph, "domains", [])
        ],
        "job": (job.to_dict() if (job := _criteria_job(access.ws.slug)) else None),
    }


@router.put("/criteria", dependencies=[auth.EDIT])
def save_criteria(body: CriteriaBody, access: auth.Access = auth.EDIT) -> dict:
    """Save a teacher's correction as the curated criteria, which win over the draft from now on."""
    if _criteria_job(access.ws.slug) is not None:
        raise HTTPException(409, "Se están redactando los criterios; espera a que terminen.")
    tutor_prompts = tutor_prompts_pkg.of(_language(access))
    document, warnings = criteria_store.normalize(
        body.criteria, _graph(access), tutor_prompts.DEFAULT_ADMINISTRATIVE_REPLY
    )
    document.pop("built", None)
    storage.write_json(
        paths.criteria_path(access.ws), document, ws=access.ws, artifact=paths.CRITERIA_STEM
    )
    return {"origin": criteria_store.CURATED, "criteria": document, "warnings": warnings}


@router.post("/criteria/build", dependencies=[auth.EDIT])
def build_criteria(access: auth.Access = auth.EDIT) -> dict:
    """Queue the drafting of the criteria from the artifacts; a curated copy will be retired."""
    _require_engine()
    error = _chain_error(access)
    if error:
        raise HTTPException(409, error)
    if _criteria_job(access.ws.slug) is not None:
        raise HTTPException(409, "Los criterios ya se están redactando.")
    job = singletons.runner.submit(
        jobs.CRITERIA,
        {},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    return {"job": job.to_dict(), "queue_position": singletons.runner.queue_position(job.id)}


@router.get("/syllabus")
def syllabus(access: auth.Access = auth.VIEW) -> dict:
    """Answer the subject's units and the concepts a student may choose a message to be about.

    The graph's own order, which is the syllabus's. Only what a conversation can stand on:
    a generic concept names no topic anybody can work on (`turn.run_turn` never takes one as
    a focus), and a unit left with none is not listed.
    """
    graph = _graph(access)
    generic = set(graph.generic_non_taggable_concepts)
    units = [
        {"name": unit, "concepts": [c for c in graph.concepts_by_domains.get(unit, []) if c not in generic]}
        for unit in graph.domains
    ]
    return {"units": [unit for unit in units if unit["concepts"]]}


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one of your conversations whole, with where its pending reply stands."""
    return _detail(_heal(access, _require(conversation_id, access)))


@router.post("/conversations/{conversation_id}/messages")
def send(
    conversation_id: str,
    body: MessageBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Append a message to one of your conversations and queue the tutor's reply."""
    message = _checked_message(body.message, access)
    concept = _checked_concept(body.concept, access)
    with store.lock_for(access.ws, access.user.id, conversation_id):
        record = _heal(access, _require(conversation_id, access), locked=True)
        _admit(access, db)
        if record.get("pending"):
            raise HTTPException(409, "El tutor todavía está contestando el mensaje anterior.")
        turn = store.append_student(record, message, concept=concept)
        store.write(access.ws, access.user.id, record)
        job = _queue_turn(access, db, record, turn)
    return {"conversation": _detail(record), "job": job.to_dict()}


@router.post("/conversations/{conversation_id}/retry")
def retry(
    conversation_id: str, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Ask again for the reply to your last message, when it got none."""
    with store.lock_for(access.ws, access.user.id, conversation_id):
        record = _heal(access, _require(conversation_id, access), locked=True)
        _admit(access, db)
        turns = record["turns"]
        if record.get("pending") or not turns or not turns[-1].get("failed"):
            raise HTTPException(409, "Ese mensaje no espera una nueva respuesta.")
        turns[-1].pop("failed", None)
        job = _queue_turn(access, db, record, len(turns) - 1)
    return {"conversation": _detail(record), "job": job.to_dict()}


@router.delete("/conversations/{conversation_id}/turn")
def cancel_turn(conversation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Stop the reply on its way; the message stays, marked as unanswered."""
    record = _require(conversation_id, access)
    pending = record.get("pending") or {}
    if not pending:
        return {"cancelled": False}
    cancelled = singletons.runner.cancel(str(pending.get("job_id")))
    _heal(access, record)
    return {"cancelled": cancelled}


@router.delete("/conversations/{conversation_id}")
def remove(conversation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Delete one of your conversations, unless a reply to it is still on its way."""
    record = _heal(access, _require(conversation_id, access))
    if record.get("pending"):
        raise HTTPException(409, "Espera a que el tutor conteste, o detén la respuesta, antes de borrarla.")
    store.delete(access.ws, access.user.id, conversation_id)
    return {"deleted": conversation_id}


# WHAT THE ROUTES SHARE -----------------------------------------------------------------


def _require(conversation_id: str, access: auth.Access) -> dict:
    """Load one of YOUR conversations of this workspace, or 404 — the same for any other."""
    return shared.require(TUTOR, conversation_id, access)


def _admit(access: auth.Access, db: DbSession) -> None:
    """Refuse a turn the queue could not or should not take, before anything is written.

    The engine has to answer, the construction has to be closed, the account may have one
    reply on its way in this workspace at a time, and it must be under the installation's
    daily limit.
    """
    _require_engine()
    error = _chain_error(access)
    if error:
        raise HTTPException(409, error)
    shared.admit(TUTOR, access, db)


def _queue_turn(access: auth.Access, db: DbSession, record: dict, turn: int) -> Job:
    """Queue the reply to one student turn, count it and record it as pending, under the caller's lock."""
    return shared.queue_turn(TUTOR, access, db, record, turn)


def _heal(access: auth.Access, record: dict, locked: bool = False) -> dict:
    """Free a conversation whose pending reply's job is over or gone, saying why on the turn."""
    return shared.heal(TUTOR, access, record, locked)


def _detail(record: dict) -> dict:
    """Render a conversation for its author: every turn, without the prompts it was made with."""
    return shared.detail(record, _row(record))


def _row(record: dict) -> dict:
    """Render a conversation as a list shows it, with the concepts it stands on."""
    return {
        **shared.row(record),
        "focus": list((record.get("state") or {}).get("focus") or []),
    }


def _checked_message(message: str, access: auth.Access) -> str:
    """Return a message trimmed, or refuse it when it is empty or longer than allowed."""
    return shared.checked_message(TUTOR, message)


def _checked_concept(concept: str | None, access: auth.Access) -> str | None:
    """Return the concept a message was sent about, or refuse one the syllabus does not offer."""
    name = (concept or "").strip()
    if not name:
        return None
    graph = _graph(access)
    if name not in graph.concept_domain or name in graph.generic_non_taggable_concepts:
        raise HTTPException(422, f"«{name}» no es un concepto que se pueda elegir en esta asignatura.")
    return name


def _require_engine() -> None:
    """Refuse with 503 when the engine does not answer: no turn could be written."""
    shared.require_engine()


def _chain_error(access: auth.Access) -> str | None:
    """Say which construction steps still have to be closed before the tutor can answer."""
    state = singletons.approvals(access.ws)
    if state.generation_unlocked():
        return None
    pending = [
        approvals.LABELS[artifact]
        for artifact in approvals.ARTIFACTS
        if state.state(artifact)["status"] != "approved"
    ]
    return f"Para usar el tutor hay que dar antes por buenos: {', '.join(pending)}."


def _criteria_job(slug: str) -> Job | None:
    """Return the live criteria job of this workspace, if one is queued or running."""
    for job in [*singletons.runner.running(slug), *singletons.runner.pending(slug)]:
        if job.kind == jobs.CRITERIA:
            return job
    return None


def _graph(access: auth.Access) -> KnowledgeGraph:
    """Return the workspace's graph as the tutor validates against it, loaded from its file."""
    path = entrypoints.knowledge_graph_path(access.ws)
    if path is None:
        raise HTTPException(409, "Esta asignatura no tiene temario todavía.")
    return KnowledgeGraph(path)


def _language(access: auth.Access) -> str:
    """Return the workspace's prompt language, which the tutor's fixed texts are written in."""
    return locale.prompt_language(access.ws)
