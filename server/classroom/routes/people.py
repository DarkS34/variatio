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

Each gesture is `server/classroom/members.py`'s, which is where the subject keeps an active
owner and an open socket of the person closes. Nobody acts here on their own membership:
leaving is `DELETE /api/workspaces/{slug}/membership`. The class's groups, what its students
use, and the class link and the personal invitations are the three modules beside this one
(`groups.py`, `uses.py`, `links.py`), under the same prefix; a fixed path of theirs is never
read as a person's id.
"""


from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ... import auth
from ...auth import queries
from ...db.models import OWNER, ROLES, VIEWER, Membership, User
from .. import groups, members
from ..members import Refusal
from ..shared import _display, _groups_view, _http, _iso

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[auth.EDIT])

DISABLE = "disable"
REMOVE = "remove"
# The bulk gesture that puts students in a group, or takes them out of theirs.
GROUP = "group"

_ACTIONS = {
    DISABLE: members.disable_member,
    "enable": members.enable_member,
    REMOVE: members.remove_member,
}


class RoleBody(BaseModel):
    """The role a member is given: `viewer`, `editor` or `owner`."""

    role: str


class BulkBody(BaseModel):
    """One gesture over several people: `disable`, `enable`, `remove`, or `group`.

    `group` puts each in `group_id`, or takes them out of theirs when it is None.
    """

    action: str
    user_ids: list[int]
    group_id: int | None = None


@router.get("")
def listing(access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the subject's people, the paused ones included, by username, and its groups."""
    rows = queries.members_of(db, access.workspace.id, include_disabled=True)
    inviters = {row.invited_by for row, _ in rows if row.invited_by is not None}
    names = {user_id: _display(db, user_id) for user_id in inviters}
    placed = groups.placed(db, access.workspace)
    return {
        "members": [_view(row, user, names, placed.get(user.id)) for row, user in rows],
        "groups": _groups_view(db, access),
    }


@router.post("/bulk")
def bulk(body: BulkBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Do one gesture to each person named, and say which were done and which refused, and why.

    Person by person, each under the rules of a single one: a refusal stops nobody else's.
    """
    if body.action not in _ACTIONS and body.action != GROUP:
        raise HTTPException(422, f"Gesto desconocido: '{body.action}'.")
    group = None
    if body.action == GROUP and body.group_id is not None:
        try:
            group = groups.get(db, access.workspace, body.group_id)
        except Refusal as refusal:
            raise _http(refusal) from None
    done: list[int] = []
    refused: list[dict] = []
    for user_id in dict.fromkeys(body.user_ids):
        try:
            if body.action == GROUP:
                _place(db, access, user_id, group)
            else:
                _act(db, access, user_id, body.action)
        except Refusal as refusal:
            refused.append({"user_id": user_id, "code": refusal.code, "reason": refusal.message})
        else:
            done.append(user_id)
    if body.action == GROUP and done:
        logger.info(
            "[asignatura] «{}» {} a {} alumno(s) {} en «{}»",
            access.user.username,
            "movió" if group else "sacó",
            len(done),
            f"al grupo «{group.name}»" if group else "de su grupo",
            access.ws.slug,
        )
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


def _place(db: DbSession, access: auth.Access, user_id: int, group) -> None:
    """Put one student in a group, or take them out of theirs."""
    member = queries.get_user_by_id(db, user_id)
    if member is None:
        raise Refusal(404, "not_found", "Esa persona no está en esta asignatura.")
    groups.place(db, access.workspace, member, group)


def _single(db: DbSession, access: auth.Access, user_id: int, action: str) -> dict:
    """Do one gesture to one person and answer the list as it now stands."""
    try:
        _act(db, access, user_id, action)
    except Refusal as refusal:
        raise _http(refusal) from None
    return listing(access=access, db=db)


def _act(db: DbSession, access: auth.Access, user_id: int, action: str) -> None:
    """Do one gesture to one person, refusing what this teacher may not do to them."""
    member = queries.get_user_by_id(db, user_id)
    row = queries.membership(db, access.workspace.id, user_id) if member else None
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
    member = queries.get_user_by_id(db, user_id)
    if member is None:
        raise HTTPException(404, "Esa persona no está en esta asignatura.")
    return member


def _view(row: Membership, user: User, names: dict[int, str], group=None) -> dict:
    """Render one person as the class list shows them: who, as what, since when, how, where."""
    return {
        "user_id": user.id,
        "name": user.name,
        "username": user.username,
        "role": row.role,
        "joined_at": _iso(row.created_at),
        "via": row.via,
        "invited_by": names.get(row.invited_by) if row.invited_by is not None else None,
        "disabled_at": _iso(row.disabled_at),
        "group": {"id": group.id, "name": group.name} if group is not None else None,
    }
