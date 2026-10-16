"""The administrator's read of the tutor's conversations: every account's, read-only.

The one exception to "a conversation is its author's", and the same one the generated
exercises make: the installation administrator, from the panel, reading. Nothing here sends,
deletes or cancels — those stay the author's — and nothing here is reachable by a member
however senior: `require_admin` guards the whole router, and the author's own routes refuse
the administrator as they refuse anyone else.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from server import auth, installation
from server.db import identity, repository

from . import store

router = APIRouter(
    prefix="/api/admin/workspaces/{slug}/tutor",
    tags=["tutor", "admin"],
    dependencies=[Depends(auth.require_admin)],
)


@router.get("")
def conversations(
    slug: str,
    author: int | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one page of every conversation held in this workspace, with its author."""
    ws = _workspace(slug, db)
    accounts = {user.id: user for user in identity.list_users(db)}
    pairs = store.list_all(ws, author=author)
    return {
        "workspace": slug,
        "conversations": [
            {**_row(record), "author": _author(user_id, accounts)}
            for user_id, record in pairs[offset : offset + limit]
        ],
        "total": len(pairs),
        "limit": limit,
        "offset": offset,
        "authors": [_author(user_id, accounts) for user_id in store.authors(ws)],
    }


@router.get("/{author_id}/{conversation_id}")
def conversation(slug: str, author_id: int, conversation_id: str, db: DbSession = Depends(auth.db)) -> dict:
    """Answer one conversation whole, as its author reads it, with how each reply was made."""
    ws = _workspace(slug, db)
    record = store.get(ws, author_id, conversation_id)
    if record is None:
        raise HTTPException(404, "Esa conversación no existe.")
    accounts = {user.id: user for user in identity.list_users(db)}
    return {**_row(record), "author": _author(author_id, accounts), "turns": record.get("turns") or []}


def _workspace(slug: str, db: DbSession):
    """Resolve a workspace the installation knows, or 404."""
    if repository.get_workspace(db, slug) is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    return installation.workspace_for(slug)


def _row(record: dict) -> dict:
    """Render a conversation as the panel's list shows it."""
    turns = record.get("turns") or []
    return {
        "id": record.get("id"),
        "title": record.get("title") or "",
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "turns": len(turns),
        "focus": list((record.get("state") or {}).get("focus") or []),
    }


def _author(user_id: int, accounts: dict) -> dict:
    """Render an author by id, with the name and username when the account still exists."""
    user = accounts.get(user_id)
    return {
        "id": user_id,
        "name": getattr(user, "name", None),
        "username": getattr(user, "username", None),
    }
