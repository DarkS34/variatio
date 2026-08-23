"""The variants this workspace has produced, kept so they can be read back.

Until phase 3 a generated item lived exactly as long as the job result that carried it:
reload the tab and a minute of GPU was gone. Every validated item is now a row, with the
commission that produced it — concepts, curriculum, fixed fields, extra instructions and
whether the model deliberated — because a variant without its parameters cannot be judged
and cannot be reproduced.

Two scopes, and the default is the narrow one. `mine` answers «lo que yo he generado»,
which is what somebody looking for the exercise they wrote yesterday means; `workspace`
answers «lo que hay en esta asignatura», which is what a shared instance is for. Neither
crosses a workspace boundary: `require_member` resolved that before this module ran.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from .. import auth
from ..db import generations as db_generations
from ..db.models import OWNER, Generation

router = APIRouter(prefix="/api/generations", tags=["generations"], dependencies=[auth.VIEW])


def _view(row: Generation, user, include_item: bool = True) -> dict:
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
        "author": {
            "id": row.user_id,
            "name": user.name if user is not None else None,
            "username": user.username if user is not None else None,
        },
    }
    if include_item:
        payload["item"] = row.item or {}
        payload["checks"] = row.checks
    return payload


@router.get("")
def listing(
    scope: str = Query("mine", pattern="^(mine|workspace)$"),
    concept: str | None = None,
    item_type: str | None = None,
    q: str | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    author = access.user.id if scope == "mine" else None
    rows, total = db_generations.list_generations(
        db,
        access.workspace.id,
        author=author,
        concept=concept,
        item_type=item_type,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {
        "generations": [_view(row, user) for row, user in rows],
        # `total` is what the current scope and filters match; `workspace_total` is the
        # whole instance, so «mías: 3» can be read against «aquí hay 40» without a second
        # request.
        "total": total,
        "workspace_total": db_generations.count_generations(db, access.workspace.id),
        "limit": limit,
        "offset": offset,
        "scope": scope,
    }


@router.get("/{generation_id}")
def detail(
    generation_id: int,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    row = _require(db, generation_id, access)
    return {
        "generation": {**_view(row, row.user), "thinking": row.thinking},
    }


# Its author, or an owner tidying up the instance. An editor deleting a colleague's
# variant would be a silent loss of somebody else's work with no way to notice it.
@router.delete("/{generation_id}", dependencies=[auth.EDIT])
def remove(
    generation_id: int,
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    row = _require(db, generation_id, access)
    if row.user_id != access.user.id and access.role != OWNER:
        raise HTTPException(403, "Solo quien la generó, o el propietario, puede borrarla.")
    db_generations.delete_generation(db, row)
    return {"deleted": generation_id}


def _require(db: DbSession, generation_id: int, access: auth.Access) -> Generation:
    row = db_generations.get_generation(db, generation_id)
    if row is None or row.workspace_id != access.workspace.id:
        raise HTTPException(404, "Esa variante no existe.")
    return row
