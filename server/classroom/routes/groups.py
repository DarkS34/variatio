"""The groups of a class, for its teachers: making, renaming and deleting them.

Declares `auth.EDIT` for the whole router, as the class list does. GROUPS OF THE CLASS
(2026-10-14, the user's decision: with a group a teacher does what they do with the class).
The bulk gesture `group` puts students in one or takes them out (`people.py`); `?group=<id>`
scopes what the students use, the class link and the personal invitations to one group, each
group with its own live link. The gestures are `server/classroom/groups.py`'s.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ... import auth
from ...bank import marks as bank_marks
from .. import groups
from ..members import Refusal
from ..shared import _groups_view, _http

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[auth.EDIT])


class GroupBody(BaseModel):
    """A group's name."""

    name: str


# THE GROUPS -------------------------------------------------------------------------------------
#
# Fixed paths: no `{user_id:int}` matches a word.


@router.get("/groups")
def group_listing(access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the subject's groups, each with how many active students it holds."""
    return {"groups": _groups_view(db, access)}


@router.post("/groups", status_code=201)
def create_group(body: GroupBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Make a new group of the class."""
    try:
        groups.create(db, access.workspace, body.name, access.user)
    except Refusal as refusal:
        raise _http(refusal) from None
    return {"groups": _groups_view(db, access)}


@router.patch("/groups/{group_id:int}")
def rename_group(
    group_id: int, body: GroupBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Give a group another name."""
    try:
        groups.rename(db, access.workspace, groups.get(db, access.workspace, group_id), body.name)
    except Refusal as refusal:
        raise _http(refusal) from None
    return {"groups": _groups_view(db, access)}


@router.delete("/groups/{group_id:int}")
def delete_group(group_id: int, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Delete a group: its students stay with no group, and its live link stops working.

    What of the bank it alone saw is hidden again (`bank_marks.forget_group`).
    """
    try:
        groups.delete_group(db, access.workspace, groups.get(db, access.workspace, group_id), access.user)
    except Refusal as refusal:
        raise _http(refusal) from None
    bank_marks.forget_group(access.ws, group_id)
    return {"groups": _groups_view(db, access)}
