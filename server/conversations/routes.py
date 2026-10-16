"""What the routes of a conversational function share: one's own conversation, a turn queued,
a conversation freed when its job is gone, and how both look on the wire.

EVERY CONVERSATION ROUTE IS SCOPED TO THE ACCOUNT THAT ASKS: the author's directory is the
only one read, and another account's conversation, another workspace's and a malformed id
all answer the same 404.

A message is answered by a job of the queue, so it waits behind a build on the local lane like
any other model call. Two rules keep the queue from filling with one person's turns: one
reply at a time per conversation (409 while it is live) and one per account in the workspace,
and the installation's daily limit per account and function (429 when it is reached).
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session as DbSession

from server import auth
from server.core import process
from server.jobs.catalogue import Job
from variatio.core import inference

from .store import Store, mark_failed
from .usage import Limit

_LIVE = ("queued", "running")


@dataclass(frozen=True)
class Function:
    """One conversational function as its routes need it.

    `daily` and `max_chars` read the function's settings when called, so a value the panel
    just changed is the one a request meets.
    """

    store: Store
    limit: Limit
    turn: str
    # The 409 when the account has another reply of this function on its way here.
    busy: str
    daily: Callable[[], int | None]
    max_chars: Callable[[], int]


def require(fn: Function, conversation_id: str, access: auth.Access) -> dict:
    """Load one of YOUR conversations of this workspace, or 404 — the same for any other."""
    record = fn.store.get(access.ws, access.user.id, conversation_id)
    if record is None:
        raise HTTPException(404, "Esa conversación no existe.")
    return record


def admit(fn: Function, access: auth.Access, db: DbSession) -> None:
    """Refuse a turn the queue should not take: one reply on its way, or the day's limit.

    The engine and, for a function that needs them, the artifacts are the caller's to check
    first.
    """
    for job in [*process.runner.running(access.ws.slug), *process.runner.pending(access.ws.slug)]:
        if job.kind == fn.turn and job.user_id == access.user.id:
            raise HTTPException(409, fn.busy)
    refused = fn.limit.refusal(db, access.user.id, fn.daily())
    if refused:
        message, wait = refused
        raise HTTPException(
            429, message, headers={"X-Error-Code": fn.limit.code, "Retry-After": str(wait)}
        )


def queue_turn(fn: Function, access: auth.Access, db: DbSession, record: dict, turn: int) -> Job:
    """Queue the reply to one student turn, count it and record it as pending, under the caller's lock."""
    job = process.runner.submit(
        fn.turn,
        {"conversation": record["id"], "turn": turn},
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    fn.limit.record(db, access.user.id)
    record["pending"] = {"job_id": job.id, "turn": turn}
    fn.store.write(access.ws, access.user.id, record)
    return job


def heal(fn: Function, access: auth.Access, record: dict, locked: bool = False) -> dict:
    """Free a conversation whose pending reply's job is over or gone, saying why on the turn.

    A job that succeeded clears the field itself; one cancelled while still queued never ran
    its handler, and one lost to a restart is unknown to the queue — both would otherwise
    hold the conversation shut for good.
    """
    pending = record.get("pending") or {}
    if not pending:
        return record
    job = process.runner.get(str(pending.get("job_id")))
    if job is not None and job.status in _LIVE:
        return record
    if job is not None and job.status == "succeeded":
        return fn.store.get(access.ws, access.user.id, record["id"]) or record
    reason = job.status if job is not None else "interrupted"

    def free() -> dict:
        """Mark the turn and write the record, reading it fresh first."""
        fresh = fn.store.get(access.ws, access.user.id, record["id"]) or record
        if (fresh.get("pending") or {}).get("job_id") == pending.get("job_id"):
            mark_failed(fresh, int(pending.get("turn", -1)), reason)
            fn.store.write(access.ws, access.user.id, fresh)
        return fresh

    if locked:
        healed = free()
    else:
        with fn.store.lock_for(access.ws, access.user.id, record["id"]):
            healed = free()
    record.clear()
    record.update(healed)
    return record


def detail(record: dict, row: dict) -> dict:
    """Render a conversation for its author: every turn, without the prompts it was made with."""
    pending = record.get("pending") or None
    job = process.runner.get(str(pending["job_id"])) if pending else None
    return {
        **row,
        "opened_from": record.get("opened_from") or {"kind": "message"},
        "state": record.get("state") or {},
        "turns": [{k: v for k, v in turn.items() if k != "prompt"} for turn in record.get("turns") or []],
        "pending": {
            **pending,
            "status": job.status if job else None,
            "queue_position": process.runner.queue_position(job.id) if job else 0,
            "job": job.to_dict() if job else None,
        }
        if pending
        else None,
    }


def row(record: dict) -> dict:
    """Render a conversation as a list shows it."""
    turns = record.get("turns") or []
    return {
        "id": record.get("id"),
        "title": record.get("title") or "",
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "turns": len(turns),
        "pending": bool(record.get("pending")),
    }


def checked_message(fn: Function, message: str) -> str:
    """Return a message trimmed, or refuse it when it is empty or longer than allowed."""
    text = (message or "").strip()
    if not text:
        raise HTTPException(422, "El mensaje está vacío.")
    limit = fn.max_chars()
    if len(text) > limit:
        raise HTTPException(422, f"Un mensaje no puede pasar de {limit} caracteres; lleva {len(text)}.")
    return text


def require_engine() -> None:
    """Refuse with 503 when the engine does not answer: no turn could be written."""
    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia '{inference.engine_name()}'. "
            "Vuelve a intentarlo en un momento.",
        )
