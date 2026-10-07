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

A TEACHER BRINGS THEIR CLASS IN WITHOUT THE ADMINISTRATOR, through two kinds of link. The
class link is one link for many students: seats, an expiry, a pause, one live per subject,
renewed by revoking it. The personal invitations are the administrator's table, scoped to
this subject: one per name, a student's — a teacher's only when an owner mints it — and no
optional function on them, which stay the administrator's to give. Both are kept sealed like
the administrator's and read again on a request of its own that leaves a line in the log. An
invitation of another subject is a 404 here.

WHAT THE STUDENTS USE is the teachers' too: whether the subject's students generate exercises
and use the tutor (`/uses`, the two switches `server/features.py` reads), closed during an
exam, say. The tutor's switch matters only where the administrator opened the tutor to one of
them, and the answer says whether that is so.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import auth, features, installation, members
from ..auth import links
from ..auth.rate_limit import throttle
from ..db import identity
from ..db.models import (
    EDITOR,
    OWNER,
    ROLES,
    STUDENT,
    TEACHER,
    VIEWER,
    ClassLink,
    Invite,
    Membership,
    User,
)
from ..members import Refusal

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[auth.EDIT])

DISABLE = "disable"
REMOVE = "remove"

_ACTIONS = {
    DISABLE: members.disable_member,
    "enable": members.enable_member,
    REMOVE: members.remove_member,
}


class RoleBody(BaseModel):
    """The role a member is given: `viewer`, `editor` or `owner`."""

    role: str


class BulkBody(BaseModel):
    """One gesture over several people: `disable`, `enable` or `remove`."""

    action: str
    user_ids: list[int]


class EndCourseBody(BaseModel):
    """How a course ends: its students paused (`disable`, undone by opening them) or removed."""

    action: str = DISABLE


class ClassLinkBody(BaseModel):
    """A class link's terms: its seats and its expiry, the defaults when absent."""

    max_uses: int | None = None
    expires_at: datetime | None = None


class ClassLinkEditBody(BaseModel):
    """New terms for the live class link; only the fields sent are read."""

    paused: bool | None = None
    max_uses: int | None = None
    expires_at: datetime | None = None


class UsesBody(BaseModel):
    """What the subject's students may use; only the fields sent change."""

    generate: bool | None = None
    tutor: bool | None = None


class InvitesBody(BaseModel):
    """Personal invitations, one per name: the name is the alias the class list reads."""

    names: list[str]
    role: str = VIEWER
    expires_at: datetime | None = None


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


# THE CLASS LINK ---------------------------------------------------------------------------------
#
# Every fixed path here is a different shape from `/{user_id:int}`, which no word matches.


@router.post("/end-course", dependencies=[auth.MANAGE])
def end_course(
    body: EndCourseBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """End the course: every active student paused, or removed, and the class link paused.

    The teachers stay, and so do the files: what each student produced is still theirs, and a
    paused course reopens by opening its students again. A student the service refuses is
    counted out, never a reason to stop half way.
    """
    if body.action not in (DISABLE, REMOVE):
        raise HTTPException(422, f"Fin de curso desconocido: '{body.action}'.")
    students = [
        user for row, user in identity.members_of(db, access.workspace.id) if row.role == VIEWER
    ]
    done = 0
    for student in students:
        try:
            _ACTIONS[body.action](db, access.workspace, student, access.user)
        except Refusal:
            continue
        done += 1
    link = identity.live_class_link(db, access.workspace.id)
    paused = link is not None and link.paused_at is None
    if paused:
        identity.edit_class_link(db, link, paused_at=identity.now())
    logger.info(
        "[asignatura] «{}» terminó el curso de «{}»: {} alumno(s) {}",
        access.user.username,
        access.ws.slug,
        done,
        "desactivado(s)" if body.action == DISABLE else "quitado(s)",
    )
    return {"action": body.action, "students": done, "class_link_paused": paused}


@router.get("/uses")
def uses(access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Answer what the subject's students may use, and whether the tutor is theirs to use at all."""
    return _uses_view(db, access)


@router.patch("/uses")
def change_uses(
    body: UsesBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Open or close generating and the tutor to the subject's students; teachers keep both."""
    changes = body.model_dump(exclude_none=True)
    features.set_subject_uses(db, access.workspace, changes)
    for feature, value in changes.items():
        logger.info(
            "[asignatura] «{}» {} {} a los alumnos de «{}»",
            access.user.username,
            "abrió" if value else "cerró",
            "la generación" if feature == features.GENERATE else "el tutor",
            access.ws.slug,
        )
    return _uses_view(db, access)


def _uses_view(db: DbSession, access: auth.Access) -> dict:
    """Render the two switches, and whether the administrator opened the tutor to a student here."""
    return {
        **features.subject_uses(access.workspace),
        "tutor_offered": features.offered_to_students(db, access.workspace),
    }


@router.get("/class-link")
def class_link(access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the subject's live class link — seats, expiry, pause, who minted it — never the link."""
    link = identity.live_class_link(db, access.workspace.id)
    return {"class_link": _link_view(db, link) if link is not None else None}


@router.get("/class-link/link")
def class_link_url(
    request: Request, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Answer the live class link itself, opened from its sealed copy, and say who read it."""
    link = identity.live_class_link(db, access.workspace.id)
    if link is None:
        raise HTTPException(404, "Esta asignatura no tiene enlace de clase.")
    token = links.unseal(link.token_sealed, link.token_hash)
    if token is None:
        raise HTTPException(
            409,
            "No se puede abrir el enlace guardado: la clave con la que se cifró ya no está. "
            "Renueva el enlace para tener uno nuevo.",
        )
    logger.info(
        "[asignatura] «{}» consultó el enlace de clase de «{}»", access.user.username, access.ws.slug
    )
    return {"link": links.url_for(auth.base_url(request), token)}


@router.post("/class-link", status_code=201)
def mint_class_link(
    body: ClassLinkBody,
    request: Request,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Mint the subject's class link, or renew it: the live one stops working, and whoever
    entered through it stays."""
    seats = _seats(body.max_uses, installation.CLASS_LINK_DEFAULT_SEATS)
    expires_at = _expiry(body.expires_at, installation.CLASS_LINK_DEFAULT_DAYS)
    throttle("teacher_invite", request, access.user.username)
    previous = identity.live_class_link(db, access.workspace.id)
    if previous is not None:
        identity.revoke_class_link(db, previous)
    link, token = links.mint_class_link(
        db,
        workspace_id=access.workspace.id,
        expires_at=expires_at,
        max_uses=seats,
        created_by=access.user.id,
    )
    logger.info(
        "[asignatura] «{}» {} el enlace de clase de «{}» · {} plazas",
        access.user.username,
        "renovó" if previous is not None else "creó",
        access.ws.slug,
        seats,
    )
    return {
        "class_link": _link_view(db, link),
        "link": links.url_for(auth.base_url(request), token),
        "stored": link.token_sealed is not None,
    }


@router.patch("/class-link")
def edit_class_link(
    body: ClassLinkEditBody, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Pause or resume the live class link, or change its seats or its expiry.

    Its seats never go below the ones already taken: whoever entered stays in.
    """
    link = identity.live_class_link(db, access.workspace.id)
    if link is None:
        raise HTTPException(404, "Esta asignatura no tiene enlace de clase.")
    sent = body.model_fields_set
    changes: dict = {}
    if "max_uses" in sent:
        seats = _seats(body.max_uses, link.max_uses)
        if seats < link.uses:
            raise HTTPException(
                422,
                f"Ya han entrado {link.uses}: las plazas no pueden ser menos que las ocupadas.",
            )
        changes["max_uses"] = seats
    if "expires_at" in sent:
        if body.expires_at is None:
            raise HTTPException(422, "Un enlace de clase siempre tiene fecha de caducidad.")
        changes["expires_at"] = _expiry(body.expires_at, installation.CLASS_LINK_DEFAULT_DAYS)
    if "paused" in sent and body.paused is not None:
        changes["paused_at"] = identity.now() if body.paused else None
    link = identity.edit_class_link(db, link, **changes)
    return {"class_link": _link_view(db, link)}


@router.delete("/class-link")
def revoke_class_link(access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Retire the live class link: it stops working at once, and whoever entered stays."""
    link = identity.live_class_link(db, access.workspace.id)
    if link is None:
        return {"revoked": False}
    identity.revoke_class_link(db, link)
    logger.info("[asignatura] «{}» retiró el enlace de clase de «{}»", access.user.username, access.ws.slug)
    return {"revoked": True}


# PERSONAL INVITATIONS ---------------------------------------------------------------------------


@router.get("/invites")
def invites(access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the subject's personal invitations nobody has used yet, live and expired alike."""
    moment = identity.now()
    rows = identity.unused_invites(db, access.workspace.id)
    return {"invites": [_invite_view(db, row, moment) for row in rows]}


@router.post("/invites", status_code=201)
def mint_invites(
    body: InvitesBody,
    request: Request,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Mint one personal invitation per name and answer the links that ARE them.

    A student's; a teacher's (`editor`) only when an owner mints it, and the account it then
    creates is a teacher's too. No optional function rides on them: that is the administrator's.
    """
    names = [" ".join(name.split()) for name in body.names]
    names = [name for name in names if name]
    if not 1 <= len(names) <= installation.INVITE_BATCH_MAX:
        raise HTTPException(
            422,
            f"Se pueden crear entre 1 y {installation.INVITE_BATCH_MAX} invitaciones a la vez.",
        )
    for name in names:
        error = identity.label_error(name)
        if error:
            raise HTTPException(422, f"«{name[:40]}…»: {error}")
    if body.role not in (VIEWER, EDITOR):
        raise HTTPException(422, f"Papel desconocido: '{body.role}'.")
    if body.role == EDITOR and not auth.at_least(access, OWNER):
        raise HTTPException(
            403,
            "Solo quien es propietario de la asignatura invita a otros docentes.",
            headers={"X-Error-Code": auth.ROLE_TOO_LOW},
        )
    expires_at = _expiry(body.expires_at, installation.TEACHER_INVITE_DEFAULT_DAYS)
    throttle("teacher_invite", request, access.user.username, cost=len(names))
    base = auth.base_url(request)
    minted = []
    for name in names:
        invite, token = links.mint(
            db,
            expires_at=expires_at,
            workspace_id=access.workspace.id,
            role=body.role,
            created_by=access.user.id,
            label=name,
            profile=TEACHER if body.role == EDITOR else STUDENT,
        )
        minted.append(
            {
                "invite": _invite_view(db, invite),
                "link": links.url_for(base, token),
                "stored": invite.token_sealed is not None,
            }
        )
    logger.info(
        "[asignatura] «{}» creó {} invitación(es) personal(es) en «{}»",
        access.user.username,
        len(minted),
        access.ws.slug,
    )
    return {"invites": minted}


@router.get("/invites/{invite_id:int}/link")
def invite_link(
    invite_id: int,
    request: Request,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one of the subject's invitations' link again, and say who read it."""
    invite = _subject_invite(db, access, invite_id)
    token = links.unseal(invite.token_sealed, invite.token_hash)
    if token is None:
        raise HTTPException(
            409,
            "El enlace de esta invitación no se puede abrir: bórrala y crea otra.",
        )
    logger.info(
        "[asignatura] «{}» consultó el enlace de la invitación {}", access.user.username, invite.id
    )
    return {"link": links.url_for(auth.base_url(request), token)}


@router.delete("/invites/{invite_id:int}")
def revoke_invite(
    invite_id: int, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Withdraw one of the subject's invitations before anybody redeems it."""
    invite = _subject_invite(db, access, invite_id)
    return {"revoked": identity.revoke_invite(db, invite.id)}


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


def _subject_invite(db: DbSession, access: auth.Access, invite_id: int) -> Invite:
    """Return an unused invitation of THIS subject, or 404 — another subject's is unknown here."""
    invite = db.get(Invite, invite_id)
    if invite is None or invite.workspace_id != access.workspace.id or invite.used_at is not None:
        raise HTTPException(404, "Esa invitación no existe.")
    return invite


def _seats(asked: int | None, default: int) -> int:
    """Accept a class link's seats: from one up to the installation's ceiling."""
    seats = default if asked is None else asked
    if not 1 <= seats <= installation.CLASS_LINK_MAX_SEATS:
        raise HTTPException(
            422, f"Un enlace de clase tiene entre 1 y {installation.CLASS_LINK_MAX_SEATS} plazas."
        )
    return seats


def _expiry(value: datetime | None, default_days: int) -> datetime:
    """Resolve when a teacher's link stops working: a default, or a moment ahead within the cap.

    A moment with no zone is read as UTC, and compared as naive when the clock is (SQLite in the
    test suite), as the administrator's own invitations are.
    """
    moment = identity.now()
    if value is None:
        return moment + timedelta(days=default_days)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if moment.tzinfo is None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value <= moment:
        raise HTTPException(422, "Esa fecha de caducidad ya ha pasado: elige una que esté por llegar.")
    if value > moment + timedelta(days=installation.TEACHER_LINK_MAX_DAYS):
        raise HTTPException(
            422,
            f"Un enlace de docente caduca en {installation.TEACHER_LINK_MAX_DAYS} días como mucho.",
        )
    return value


def _link_view(db: DbSession, link: ClassLink) -> dict:
    """Render a class link for its teachers: its terms and how full it is, never its token."""
    return {
        "id": link.id,
        "uses": link.uses,
        "max_uses": link.max_uses,
        "expires_at": _iso(link.expires_at),
        "expired": link.expires_at <= identity.now(),
        "paused": link.paused_at is not None,
        "created_at": _iso(link.created_at),
        "created_by": _display(db, link.created_by) if link.created_by is not None else None,
        "link_stored": link.token_sealed is not None,
    }


def _invite_view(db: DbSession, invite: Invite, moment: datetime | None = None) -> dict:
    """Render one of the subject's personal invitations: its alias, role, expiry and author."""
    moment = moment if moment is not None else identity.now()
    return {
        "id": invite.id,
        "label": invite.label,
        "role": invite.role,
        "profile": invite.profile,
        "created_at": _iso(invite.created_at),
        "expires_at": _iso(invite.expires_at),
        "created_by": _display(db, invite.created_by) if invite.created_by is not None else None,
        "state": "pending" if invite.expires_at > moment else "expired",
        "link_stored": invite.token_sealed is not None,
    }


def _display(db: DbSession, user_id: int) -> str | None:
    """Name the account that let somebody in, by its display name; None when it is gone."""
    user = identity.get_user_by_id(db, user_id)
    return user.name if user is not None else None


def _iso(moment: datetime | None) -> str | None:
    """Render a moment as ISO 8601, or None."""
    return moment.isoformat() if moment is not None else None
