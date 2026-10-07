"""The people of a subject, for its teachers: who is in it, and pausing, opening and removing.

Declares `auth.EDIT` for the whole router: the list of people is a teacher's and never a
student's. What a teacher may do to whom follows the person's role — a teacher pauses, opens
and removes students, and a teacher or an owner is the owner's to touch (`auth.MANAGE`,
checked inside with `auth.at_least`). Changing a role is the owner's alone; handing over the
ownership is no route of its own — the owner makes another teacher owner, then lowers their
own role.

The list says who the people are and how they came in, and nothing about what they did: no
address, no figure of use. Every route already serves several teachers; their screens arrive
later. A person's id travels as `{user_id:int}`, so a fixed path beside it can never be read
as one.

Each gesture is `server/members.py`'s, which is where the subject keeps an active owner and
an open socket of the person closes. Nobody acts here on their own membership: leaving is
`DELETE /api/workspaces/{slug}/membership`.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import auth, members
from ..db import identity
from ..db.models import OWNER, ROLES, VIEWER, Membership, User
from ..members import Refusal

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[auth.EDIT])

_ACTIONS = {
    "disable": members.disable_member,
    "enable": members.enable_member,
    "remove": members.remove_member,
}


class RoleBody(BaseModel):
    """The role a member is given: `viewer`, `editor` or `owner`."""

    role: str


class BulkBody(BaseModel):
    """One gesture over several people: `disable`, `enable` or `remove`."""

    action: str
    user_ids: list[int]


@router.get("")
def listing(access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the subject's people, the paused ones included, by username."""
    rows = identity.members_of(db, access.workspace.id, include_disabled=True)
    inviters = {row.invited_by for row, _ in rows if row.invited_by is not None}
    names = {user_id: _display(db, user_id) for user_id in inviters}
    return {"members": [_view(row, user, names) for row, user in rows]}


@router.post("/bulk")
def bulk(body: BulkBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Do one gesture to each person named, and say which were done and which refused, and why.

    Person by person, each under the rules of a single one: a refusal stops nobody else's.
    """
    if body.action not in _ACTIONS:
        raise HTTPException(422, f"Gesto desconocido: '{body.action}'.")
    done: list[int] = []
    refused: list[dict] = []
    for user_id in dict.fromkeys(body.user_ids):
        try:
            _act(db, access, user_id, body.action)
        except Refusal as refusal:
            refused.append({"user_id": user_id, "code": refusal.code, "reason": refusal.message})
        else:
            done.append(user_id)
    return {"done": done, "refused": refused}


@router.patch("/{user_id:int}", dependencies=[auth.MANAGE])
def change_role(
    user_id: int, body: RoleBody, access: auth.Access = auth.MANAGE, db: DbSession = Depends(auth.db)
) -> dict:
    """Give a member another role. The owner's own included, which is how ownership is handed over."""
    if body.role not in ROLES:
        raise HTTPException(422, f"Papel desconocido: '{body.role}'.")
    member = _member(db, user_id)
    try:
        row = members.change_role(db, access.workspace, member, body.role)
    except Refusal as refusal:
        raise _http(refusal) from None
    return {"member": _view(row, member, {})}


@router.post("/{user_id:int}/disable")
def disable(user_id: int, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Pause a person's access to the subject. Reversible: `enable` gives it back as it was."""
    return _single(db, access, user_id, "disable")


@router.post("/{user_id:int}/enable")
def enable(user_id: int, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Give a paused person their access back, with the role, origin and date they had."""
    return _single(db, access, user_id, "enable")


@router.delete("/{user_id:int}")
def remove(user_id: int, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Take a person out of the subject. Their files stay; only a new link brings them back."""
    return _single(db, access, user_id, "remove")


def _single(db: DbSession, access: auth.Access, user_id: int, action: str) -> dict:
    """Do one gesture to one person and answer the list as it now stands."""
    try:
        _act(db, access, user_id, action)
    except Refusal as refusal:
        raise _http(refusal) from None
    return listing(access=access, db=db)


def _act(db: DbSession, access: auth.Access, user_id: int, action: str) -> None:
    """Do one gesture to one person, refusing what this teacher may not do to them."""
    member = identity.get_user_by_id(db, user_id)
    row = identity.membership(db, access.workspace.id, user_id) if member else None
    if member is None or row is None:
        raise Refusal(404, "not_found", "Esa persona no está en esta asignatura.")
    if member.id == access.user.id:
        raise Refusal(
            409, "self", "Para salir tú de la asignatura, usa «Salir» en «Mis asignaturas»."
        )
    if row.role != VIEWER and not auth.at_least(access, OWNER):
        raise Refusal(
            403,
            auth.ROLE_TOO_LOW,
            "Solo quien es propietario de la asignatura actúa sobre sus docentes.",
        )
    _ACTIONS[action](db, access.workspace, member, access.user)


def _member(db: DbSession, user_id: int) -> User:
    """Return the account a route names, or 404."""
    member = identity.get_user_by_id(db, user_id)
    if member is None:
        raise HTTPException(404, "Esa persona no está en esta asignatura.")
    return member


def _http(refusal: Refusal) -> HTTPException:
    """Turn a refused gesture into the answer the client reads by its code."""
    return HTTPException(refusal.status, refusal.message, headers={"X-Error-Code": refusal.code})


def _view(row: Membership, user: User, names: dict[int, str]) -> dict:
    """Render one person as the class list shows them: who, as what, since when, how."""
    return {
        "user_id": user.id,
        "name": user.name,
        "username": user.username,
        "role": row.role,
        "joined_at": _iso(row.created_at),
        "via": row.via,
        "invited_by": names.get(row.invited_by) if row.invited_by is not None else None,
        "disabled_at": _iso(row.disabled_at),
    }


def _display(db: DbSession, user_id: int) -> str | None:
    """Name the account that let somebody in, by its display name; None when it is gone."""
    user = identity.get_user_by_id(db, user_id)
    return user.name if user is not None else None


def _iso(moment: datetime | None) -> str | None:
    """Render a moment as ISO 8601, or None."""
    return moment.isoformat() if moment is not None else None
