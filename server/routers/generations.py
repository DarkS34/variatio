"""The exercises this account has generated, kept so they can be read back.

Declares `auth.VIEW` for the whole router; promoting and deleting add `auth.EDIT`.

Every validated item is a row carrying the commission that produced it — concepts,
curriculum, fixed fields, extra instructions, which model wrote it and whether it
deliberated — because a statement without its parameters can be read but neither judged nor
reproduced.

EVERY ROUTE IS SCOPED TO THE ACCOUNT THAT ASKS, and there is no second scope to flip: a
filter somebody can turn off is not privacy. The membership bounds the workspace and the
author bounds the rows inside it, so two accounts preparing one subject do not read each
other's exercises. Neither the owner nor the administrator is an exception — `_require`
answers 404 for a row that is not yours, because «existe pero no es tuya» is itself
something this refuses to say.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from .. import auth
from ..db import generations as db_generations
from ..db.models import Generation
from ..editors import bank_edit
from ..editors.bank_edit import BankError
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/generations", tags=["generations"], dependencies=[auth.VIEW])


def _view(row: Generation, user, include_item: bool = True) -> dict:
    """Render one stored variant with its commission, and optionally the item itself."""
    payload = {
        "id": row.id,
        "created_at": row.created_at.timestamp() if row.created_at else 0.0,
        "job_id": row.job_id,
        "item_type": row.item_type,
        "concepts": list(row.concepts or []),
        "curriculum": list(row.curriculum or []),
        "fixed": dict(row.fixed or {}),
        "instructions": row.instructions or "",
        "think": bool(row.think),
        # Null for every row written before a commission could choose its model: the
        # screen says nothing rather than naming today's default, which did not write it.
        "model": row.model or None,
        "author": {
            "id": row.user_id,
            "name": user.name if user is not None else None,
            "username": user.username if user is not None else None,
        },
        "promoted_item_id": row.promoted_item_id,
    }
    if include_item:
        payload["item"] = row.item or {}
        payload["checks"] = row.checks
    return payload


@router.get("")
def listing(
    concept: str | None = None,
    item_type: str | None = None,
    q: str | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one page of your own stored variants.

    `total` is what the filters match over everything you have generated here; there is no
    count of the instance's, which would report how much other people have produced.
    """
    rows, total = db_generations.list_generations(
        db,
        access.workspace.id,
        author=access.user.id,
        concept=concept,
        item_type=item_type,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {
        "generations": [_view(row, user) for row, user in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{generation_id}")
def detail(
    generation_id: int,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one stored variant, with the model's deliberation."""
    row = _require(db, generation_id, access)
    return {
        "generation": {**_view(row, row.user), "thinking": row.thinking},
    }


@router.post("/{generation_id}/promote", dependencies=[auth.EDIT])
def promote(
    generation_id: int,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Copy this variant into the exemplars bank."""
    row = _require(db, generation_id, access)
    if row.promoted_item_id and bank_edit.has_item(access.ws, row.promoted_item_id):
        raise HTTPException(
            409, f"Esta variante ya está en el banco como «{row.promoted_item_id}»."
        )
    try:
        result = bank_edit.add_item(
            access.ws,
            dict(row.item or {}),
            row.item_type or None,
            list(row.concepts or []),
        )
    except BankError as exc:
        raise HTTPException(422, str(exc)) from exc
    row.promoted_item_id = result["item"]["id"]
    db.flush()
    return {
        "generation": generation_id,
        "item": result["item"],
        "pipeline": pipeline_payload(access),
    }


@router.delete("/{generation_id}", dependencies=[auth.EDIT])
def remove(
    generation_id: int,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Delete one of your own stored variants.

    `auth.EDIT` is not enough on its own and neither is being the owner: `_require` already
    refuses a row that is not yours, so nobody can delete somebody else's work — which was
    the rule before, arrived at now by the same door that hides it.
    """
    db_generations.delete_generation(db, _require(db, generation_id, access))
    return {"deleted": generation_id}


def _require(db: DbSession, generation_id: int, access: auth.Access) -> Generation:
    """Load one of YOUR variants of this workspace, or 404.

    A row of another instance and a row of another account are both simply unknown: the
    404 is the same sentence for both, because a 403 would confirm that the id names
    something.
    """
    row = db_generations.get_generation(db, generation_id)
    if (
        row is None
        or row.workspace_id != access.workspace.id
        or row.user_id != access.user.id
    ):
        raise HTTPException(404, "Ese ejercicio no existe.")
    return row
