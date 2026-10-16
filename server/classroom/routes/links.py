"""How a teacher brings their class in: the class link and the personal invitations.

Declares `auth.EDIT` for the whole router, as the class list does. A TEACHER BRINGS THEIR
CLASS IN WITHOUT THE ADMINISTRATOR, through two kinds of link. The class link is one link for
many students: seats, an expiry, a pause, one live per subject, renewed by revoking it. The
personal invitations are the administrator's table, scoped to this subject: one per name, a
student's — a teacher's only when an owner mints it — and no optional function on them, which
stay the administrator's to give. Both are kept sealed like the administrator's and read again
on a request of its own that leaves a line in the log. An invitation of another subject is a
404 here.
"""

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ... import auth
from ...auth import links, mail, queries
from ...auth.rate_limit import throttle
from ...core import environment
from ...db.models import EDITOR, OWNER, STUDENT, TEACHER, VIEWER, ClassLink, Invite
from ..shared import _display, _group, _iso

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[auth.EDIT])


class ClassLinkBody(BaseModel):
    """A class link's terms: its seats and its expiry, the defaults when absent."""

    max_uses: int | None = None
    expires_at: datetime | None = None


class ClassLinkEditBody(BaseModel):
    """New terms for the live class link; only the fields sent are read."""

    paused: bool | None = None
    max_uses: int | None = None
    expires_at: datetime | None = None


class InvitesBody(BaseModel):
    """Personal invitations, one per name: the name is the alias the class list reads.

    `emails`, when sent, goes beside `names` line by line (None where a name has none): each
    invitation with an address is mailed, and the address is kept nowhere.
    """

    names: list[str]
    role: str = VIEWER
    expires_at: datetime | None = None
    emails: list[str | None] | None = None
    group_id: int | None = None


# THE CLASS LINK ---------------------------------------------------------------------------------
#
# Every fixed path here is a different shape from `/{user_id:int}`, which no word matches.


@router.get("/class-link")
def class_link(
    group: int | None = None, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Answer the live link of the class, or of one group — seats, expiry, pause, who minted
    it — never the link."""
    link = queries.live_class_link(db, access.workspace.id, _group_id(db, access, group))
    return {"class_link": _link_view(db, link) if link is not None else None}


@router.get("/class-link/link")
def class_link_url(
    request: Request,
    group: int | None = None,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer the live class link itself, opened from its sealed copy, and say who read it."""
    link = queries.live_class_link(db, access.workspace.id, _group_id(db, access, group))
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
    group: int | None = None,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Mint the class link, or one group's, or renew it: the live one of that destination stops
    working, and whoever entered through it stays."""
    group_id = _group_id(db, access, group)
    seats = _seats(body.max_uses, environment.CLASS_LINK_DEFAULT_SEATS)
    expires_at = _expiry(body.expires_at, environment.CLASS_LINK_DEFAULT_DAYS)
    throttle("teacher_invite", request, access.user.username)
    previous = queries.live_class_link(db, access.workspace.id, group_id)
    if previous is not None:
        queries.revoke_class_link(db, previous)
    link, token = links.mint_class_link(
        db,
        workspace_id=access.workspace.id,
        expires_at=expires_at,
        max_uses=seats,
        created_by=access.user.id,
        group_id=group_id,
    )
    logger.info(
        "[asignatura] «{}» {} el enlace {} de «{}» · {} plazas",
        access.user.username,
        "renovó" if previous is not None else "creó",
        "de un grupo" if group_id is not None else "de clase",
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
    body: ClassLinkEditBody,
    group: int | None = None,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Pause or resume the live class link, or a group's, or change its seats or its expiry.

    Its seats never go below the ones already taken: whoever entered stays in.
    """
    link = queries.live_class_link(db, access.workspace.id, _group_id(db, access, group))
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
        changes["expires_at"] = _expiry(body.expires_at, environment.CLASS_LINK_DEFAULT_DAYS)
    if "paused" in sent and body.paused is not None:
        changes["paused_at"] = queries.now() if body.paused else None
    link = queries.edit_class_link(db, link, **changes)
    return {"class_link": _link_view(db, link)}


@router.delete("/class-link")
def revoke_class_link(
    group: int | None = None, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Retire the live class link, or a group's: it stops working at once, and whoever entered
    stays."""
    link = queries.live_class_link(db, access.workspace.id, _group_id(db, access, group))
    if link is None:
        return {"revoked": False}
    queries.revoke_class_link(db, link)
    logger.info("[asignatura] «{}» retiró el enlace de clase de «{}»", access.user.username, access.ws.slug)
    return {"revoked": True}


# PERSONAL INVITATIONS ---------------------------------------------------------------------------


@router.get("/invites")
def invites(
    group: int | None = None, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Answer the subject's personal invitations nobody has used yet, live and expired alike;
    with `group`, only the ones that bring into that group."""
    moment = queries.now()
    group_id = _group_id(db, access, group)
    rows = queries.unused_invites(db, access.workspace.id)
    if group_id is not None:
        rows = [row for row in rows if row.group_id == group_id]
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

    With mail configured, a name may come with an address (`emails`): its link is sent there
    and the answer says whether it left (`sent`); the address is kept nowhere — not in the
    invitation, not in the log — so a link that did not leave is copied by hand.
    """
    if body.emails is not None and len(body.emails) != len(body.names):
        raise HTTPException(422, "Cada nombre lleva su correo, o ninguno.")
    pairs = [
        (" ".join(name.split()), (email or "").strip() or None)
        for name, email in zip(body.names, body.emails or [None] * len(body.names))
    ]
    pairs = [(name, email) for name, email in pairs if name]
    names = [name for name, _ in pairs]
    addresses = [email for _, email in pairs if email]
    if addresses and not mail.configured():
        raise HTTPException(422, "Esta instalación no envía correo: copia los enlaces a mano.")
    for email in addresses:
        if len(email) > 254 or not _EMAIL.match(email):
            raise HTTPException(422, f"«{email[:60]}» no es una dirección de correo.")
    if not 1 <= len(names) <= environment.INVITE_BATCH_MAX:
        raise HTTPException(
            422,
            f"Se pueden crear entre 1 y {environment.INVITE_BATCH_MAX} invitaciones a la vez.",
        )
    for name in names:
        error = queries.label_error(name)
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
    group_id = _group_id(db, access, body.group_id)
    if group_id is not None and body.role != VIEWER:
        raise HTTPException(422, "Los grupos son de alumnos: una invitación de docente no lleva grupo.")
    expires_at = _expiry(body.expires_at, environment.TEACHER_INVITE_DEFAULT_DAYS)
    throttle("teacher_invite", request, access.user.username, cost=len(names))
    base = auth.base_url(request)
    minted = []
    for name, email in pairs:
        invite, token = links.mint(
            db,
            expires_at=expires_at,
            workspace_id=access.workspace.id,
            role=body.role,
            created_by=access.user.id,
            label=name,
            profile=TEACHER if body.role == EDITOR else STUDENT,
            group_id=group_id,
        )
        link = links.url_for(base, token)
        row = {
            "invite": _invite_view(db, invite),
            "link": link,
            "stored": invite.token_sealed is not None,
        }
        if email:
            row["sent"] = mail.send(
                email,
                f"Invitación a «{access.workspace.name}»",
                _invitation_mail(access, body.role, link, expires_at),
                shown_as="una invitación de asignatura",
            )
        minted.append(row)
    sent = sum(1 for row in minted if row.get("sent"))
    logger.info(
        "[asignatura] «{}» creó {} invitación(es) personal(es) en «{}»{}",
        access.user.username,
        len(minted),
        access.ws.slug,
        f" · {sent} de {len(addresses)} enviada(s) por correo" if addresses else "",
    )
    return {"invites": minted}


# An address as a person writes it; delivery is the server's to prove, not this pattern's.
_EMAIL = re.compile(r"\A[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+\Z")


def _invitation_mail(access: auth.Access, role: str, link: str, expires_at: datetime) -> str:
    """Write the mail that carries one personal invitation."""
    who = "docente" if role == EDITOR else "alumno"
    return (
        f"{access.user.name or access.user.username} te invita a «{access.workspace.name}» "
        f"en Variatio, como {who}.\n\n"
        f"Abre este enlace para entrar:\n{link}\n\n"
        f"El enlace caduca el {expires_at:%d/%m/%Y} y sirve una sola vez. "
        "Si no esperabas esta invitación, no hagas nada."
    )


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
    return {"revoked": queries.revoke_invite(db, invite.id)}


def _group_id(db: DbSession, access: auth.Access, group_id: int | None) -> int | None:
    """Return the id of the group a request scopes to, checked against this subject."""
    group = _group(db, access, group_id)
    return group.id if group is not None else None


def _subject_invite(db: DbSession, access: auth.Access, invite_id: int) -> Invite:
    """Return an unused invitation of THIS subject, or 404 — another subject's is unknown here."""
    invite = db.get(Invite, invite_id)
    if invite is None or invite.workspace_id != access.workspace.id or invite.used_at is not None:
        raise HTTPException(404, "Esa invitación no existe.")
    return invite


def _seats(asked: int | None, default: int) -> int:
    """Accept a class link's seats: from one up to the installation's ceiling."""
    seats = default if asked is None else asked
    if not 1 <= seats <= environment.CLASS_LINK_MAX_SEATS:
        raise HTTPException(
            422, f"Un enlace de clase tiene entre 1 y {environment.CLASS_LINK_MAX_SEATS} plazas."
        )
    return seats


def _expiry(value: datetime | None, default_days: int) -> datetime:
    """Resolve when a teacher's link stops working: a default, or a moment ahead within the cap.

    A moment with no zone is read as UTC, and compared as naive when the clock is (SQLite in the
    test suite), as the administrator's own invitations are.
    """
    moment = queries.now()
    if value is None:
        return moment + timedelta(days=default_days)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if moment.tzinfo is None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value <= moment:
        raise HTTPException(422, "Esa fecha de caducidad ya ha pasado: elige una que esté por llegar.")
    if value > moment + timedelta(days=environment.TEACHER_LINK_MAX_DAYS):
        raise HTTPException(
            422,
            f"Un enlace de docente caduca en {environment.TEACHER_LINK_MAX_DAYS} días como mucho.",
        )
    return value


def _link_view(db: DbSession, link: ClassLink) -> dict:
    """Render a class link for its teachers: its terms and how full it is, never its token."""
    return {
        "id": link.id,
        "uses": link.uses,
        "max_uses": link.max_uses,
        "expires_at": _iso(link.expires_at),
        "expired": link.expires_at <= queries.now(),
        "paused": link.paused_at is not None,
        "created_at": _iso(link.created_at),
        "created_by": _display(db, link.created_by) if link.created_by is not None else None,
        "link_stored": link.token_sealed is not None,
        "group_id": link.group_id,
    }


def _invite_view(db: DbSession, invite: Invite, moment: datetime | None = None) -> dict:
    """Render one of the subject's personal invitations: its alias, role, expiry and author."""
    moment = moment if moment is not None else queries.now()
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
        "group_id": invite.group_id,
    }
