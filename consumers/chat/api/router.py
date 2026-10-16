"""The free chat's routes: one's own conversations, as the tutor's are.

Declares `auth.VIEW` and `auth.CHAT` for the whole router: the chat is the subject's to open
to its students (`server.auth.features`, closed until a teacher opens it), and its teachers
always have it. Every conversation route is scoped to the account that asks
(`server.conversations.routes`); a message is answered by a job of the queue, one reply at a
time per account in the workspace, under the installation's daily limit of the chat.

A conversation may open on an exercise: one of the author's generated exercises, or one of the
bank this account reads (`/api/exercises`). It keeps what the student reads of it — every
field of their own exercise, only the fields shown of the bank's — and that is what reaches
the model, never a field hidden from them.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server import auth
from server import generations as generations_store
from server.bank import edit as bank_edit
from server.bank import reading as bank_reading
from server.bank.reading import reader_of
from server.conversations import routes as shared
from server.conversations import store as shared_store
from server.core import process
from server.pipeline import approvals
from variatio.loaders.exemplars_profile import ExemplarsProfile

from .. import config as chat_config
from . import jobs, usage
from .store import STORE

router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[auth.VIEW, auth.CHAT])

CHAT = shared.Function(
    store=STORE,
    limit=usage.LIMIT,
    turn=jobs.TURN,
    busy="El chat ya está contestando otra conversación tuya; espera a que termine.",
    daily=lambda: chat_config.DAILY_MESSAGES,
    max_chars=lambda: chat_config.MESSAGE_MAX_CHARS,
)


class MessageBody(BaseModel):
    """A student's message, and the exercise a new conversation is opened on, if any."""

    message: str
    generation_id: str | None = None
    bank_id: str | None = None


@router.get("/conversations")
def conversations(access: auth.Access = auth.VIEW) -> dict:
    """Answer one's own conversations in this workspace, the most recently active first."""
    return {
        "conversations": [
            shared.row(shared.heal(CHAT, access, record)) for record in STORE.list_for(access.ws, access.user.id)
        ]
    }


@router.post("/conversations", status_code=201)
def open_conversation(
    body: MessageBody, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Start a conversation with its first message and queue the reply."""
    message = shared.checked_message(CHAT, body.message)
    if body.generation_id and body.bank_id:
        raise HTTPException(422, "Una conversación se abre sobre un ejercicio, no sobre dos.")
    opened_from = _opened_from(body, access, db)
    shared.require_engine()
    shared.admit(CHAT, access, db)
    record = STORE.create(access.ws, access.user.id, message, opened_from)
    with STORE.lock_for(access.ws, access.user.id, record["id"]):
        job = shared.queue_turn(CHAT, access, db, record, 0)
    return {"conversation": shared.detail(record, shared.row(record)), "job": job.to_dict()}


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one of your conversations whole, with where its pending reply stands."""
    record = shared.heal(CHAT, access, shared.require(CHAT, conversation_id, access))
    return shared.detail(record, shared.row(record))


@router.post("/conversations/{conversation_id}/messages")
def send(
    conversation_id: str,
    body: MessageBody,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Append a message to one of your conversations and queue the reply."""
    message = shared.checked_message(CHAT, body.message)
    with STORE.lock_for(access.ws, access.user.id, conversation_id):
        record = shared.heal(CHAT, access, shared.require(CHAT, conversation_id, access), locked=True)
        shared.require_engine()
        shared.admit(CHAT, access, db)
        if record.get("pending"):
            raise HTTPException(409, "El chat todavía está contestando el mensaje anterior.")
        turn = shared_store.append_student(record, message)
        STORE.write(access.ws, access.user.id, record)
        job = shared.queue_turn(CHAT, access, db, record, turn)
    return {"conversation": shared.detail(record, shared.row(record)), "job": job.to_dict()}


@router.post("/conversations/{conversation_id}/retry")
def retry(
    conversation_id: str, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Ask again for the reply to your last message, when it got none."""
    with STORE.lock_for(access.ws, access.user.id, conversation_id):
        record = shared.heal(CHAT, access, shared.require(CHAT, conversation_id, access), locked=True)
        shared.require_engine()
        shared.admit(CHAT, access, db)
        turns = record["turns"]
        if record.get("pending") or not turns or not turns[-1].get("failed"):
            raise HTTPException(409, "Ese mensaje no espera una nueva respuesta.")
        turns[-1].pop("failed", None)
        job = shared.queue_turn(CHAT, access, db, record, len(turns) - 1)
    return {"conversation": shared.detail(record, shared.row(record)), "job": job.to_dict()}


@router.delete("/conversations/{conversation_id}/turn")
def cancel_turn(conversation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Stop the reply on its way; the message stays, marked as unanswered."""
    record = shared.require(CHAT, conversation_id, access)
    pending = record.get("pending") or {}
    if not pending:
        return {"cancelled": False}
    cancelled = process.runner.cancel(str(pending.get("job_id")))
    shared.heal(CHAT, access, record)
    return {"cancelled": cancelled}


@router.delete("/conversations/{conversation_id}")
def remove(conversation_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Delete one of your conversations, unless a reply to it is still on its way."""
    record = shared.heal(CHAT, access, shared.require(CHAT, conversation_id, access))
    if record.get("pending"):
        raise HTTPException(409, "Espera a que el chat conteste, o detén la respuesta, antes de borrarla.")
    STORE.delete(access.ws, access.user.id, conversation_id)
    return {"deleted": conversation_id}


def _opened_from(body: MessageBody, access: auth.Access, db: DbSession) -> dict | None:
    """Name the exercise a conversation opens on, with what the student reads of it."""
    if body.generation_id:
        record = generations_store.get(access.ws, access.user.id, body.generation_id)
        if record is None:
            raise HTTPException(404, "Ese ejercicio no existe.")
        item, item_type = generations_store.item_of(record), generations_store.item_type_of(record)
        return {
            "kind": "generation",
            "generation_id": body.generation_id,
            "exercise": _fields(access, item_type, item, None),
        }
    if body.bank_id:
        group_id, every_group = reader_of(db, access)
        try:
            item = bank_reading.readable(access.ws, body.bank_id, group_id, every_group)
        except bank_edit.BankError:
            item = None
        if item is None:
            raise HTTPException(404, "Ese ejercicio no existe.")
        return {
            "kind": "bank",
            "bank_id": body.bank_id,
            "key": item["key"],
            "exercise": _fields(access, item["item_type"], item, item["shown"]),
        }
    return None


def _fields(access: auth.Access, item_type: str, item: dict, shown: list[str] | None) -> list[list[str]]:
    """Return an exercise's fields as labels and texts, in its type's order, the statement first.

    `shown` keeps only those fields (an exercise of the bank, as its teacher showed it); the
    level is always one of them. Empty fields are left out.
    """
    spec = _type(access, item_type)
    if spec is None:
        names = [name for name in (shown or item) if name in item]
    else:
        order = [spec.primary_field, *(name for name in spec.field_specs if name != spec.primary_field)]
        level = spec.difficulty_field
        names = [name for name in order if shown is None or name in shown or name == level]
    pairs = []
    for name in names:
        value = item.get(name)
        if value is None or value == "" or value == []:
            continue
        label = str(((spec.field_specs.get(name) or {}).get("label") if spec else None) or name.replace("_", " "))
        text = "\n".join(str(entry) for entry in value) if isinstance(value, list) else str(value)
        pairs.append([label, text])
    return pairs


def _type(access: auth.Access, item_type: str):
    """Return the profile's type of an exercise, or None when the profile cannot say."""
    path = approvals.current_path(access.ws, approvals.EXEMPLARS_PROFILE)
    if path is None:
        return None
    try:
        profile = ExemplarsProfile(path)
        return profile.item_types.get(item_type) or profile.item_types.get(profile.default_type)
    except (ValueError, OSError):
        return None
