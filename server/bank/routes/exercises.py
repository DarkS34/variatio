"""The bank as the class reads it: the exercises its teachers showed, and only what they showed.

Declares `auth.VIEW`: a student reads here what `/api/bank` (`auth.EDIT`, reads included)
never answers them (the user's decision, 2026-10-14). Each exercise is cut to the fields a
teacher chose to show (`server/bank/marks.py`), with its type, its level and its concepts;
never where it comes from, who added it or the tagger's trace. A student sees the exercises
shown to the whole class and those shown to their group; a teacher reading it sees the ones
shown to anybody.

The answer has the shape of `GET /api/bank` — items, types, levels, total — so the client
draws it with the same table. Filters: search, type, level, concept; the origin and «Sin
concepto» are a teacher's work, not a reader's.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from ... import auth
from .. import reading as bank_reading
from ..edit import BankError
from ..reading import reader_of

router = APIRouter(prefix="/api/exercises", tags=["exercises"], dependencies=[auth.VIEW])


@router.get("")
def listing(
    q: str | None = None,
    item_type: str | None = None,
    difficulty: str | None = None,
    concept: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    access: auth.Access = auth.VIEW,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one page of the exercises this account's class may read.

    No bank, or no profile yet, is an empty page and not a 404: for a student it is the same
    thing as nothing shown.
    """
    group_id, every_group = reader_of(db, access)
    try:
        return bank_reading.reading(
            access.ws,
            group_id,
            every_group=every_group,
            query=q,
            item_type=item_type,
            difficulty=difficulty,
            concept=concept,
            page=page,
            page_size=page_size,
        )
    except BankError:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "item_types": [],
            "difficulties": [],
            "default_type": None,
            "concepts": [],
        }


@router.get("/{item_id}")
def detail(item_id: str, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)) -> dict:
    """Answer one exercise as this account's class reads it; one not shown to it is a 404."""
    group_id, every_group = reader_of(db, access)
    try:
        item = bank_reading.readable(access.ws, item_id, group_id, every_group)
    except BankError:
        item = None
    if item is None:
        raise HTTPException(404, "Ese ejercicio no existe.")
    return {"item": item}
