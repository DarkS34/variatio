"""The administrator's invitations: minting, importing, reading again, editing and revoking them.

Behind `require_admin`, under `/api/admin` like every route of the panel. INVITATIONS AND MEMBERSHIP ARE THE INSTALLATION
ADMINISTRATOR'S ALONE: there is no owner-scoped door, because an owner owns their workspace's
content and does not decide who else exists, and two screens for one question is how an
installation ends up with two answers. A teacher mints their class's own (`classroom/`).
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import auth
from ..auth import features, links, queries
from ..auth.rate_limit import throttle
from ..core import environment
from ..db import repository
from ..db.models import EDITOR, ROLES, Invite, User, Workspace

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class InviteTerms(BaseModel):
    """What an invitation grants, until when, and the name only the panel ever reads.

    `workspace` may be absent — an invitation granting no membership creates an account
    and no access, which is the honest way to add somebody who will be given a workspace
    later. `features` lists the new account for the optional functions named
    (`server/auth/features.py`), which is access too. `profile` is what the account will be, a
    teacher or a student, and it is REQUIRED: nobody asks the person registering, and no
    default is presumed for them — a teacher creates subjects. An absent `expires_at` is
    the installation's default week, and a chosen one has no upper bound; `label` is the
    administrator's alias and never reaches the person holding the link.
    """

    workspace: str | None = None
    role: str = EDITOR
    expires_at: datetime | None = None
    label: str | None = None
    features: list[str] = []
    profile: str | None = None


class InviteBody(InviteTerms):
    """One invitation, or `count` alike — a class handed out at once."""

    count: int = 1


class InviteImportBody(InviteTerms):
    """A link somebody already holds, to be made to work again under these terms."""

    link: str


class InviteEditBody(BaseModel):
    """New terms for an invitation nobody has used; only the fields sent are read.

    `workspace: null` sent is «ninguna», which is why presence and not value decides.
    """

    workspace: str | None = None
    role: str | None = None
    expires_at: datetime | None = None
    label: str | None = None
    features: list[str] | None = None
    profile: str | None = None


# ACCESS ----------------------------------------------------------------------------------
#
# The only way an account comes into existence, and the only way one enters a workspace.


@router.get("/invites")
def invites(db: DbSession = Depends(auth.db)) -> dict:
    """List every invitation nobody has used yet, live and expired alike.

    Expired ones stay because a date can be moved, and the same link works again once it
    is. What a row never carries is its link: that is a request of its own, and a logged one.
    """
    moment = queries.now()
    return {"invites": [_invite(db, row, moment) for row in queries.unused_invites(db)]}


@router.post("/invites", status_code=201)
def create_invite(
    body: InviteBody,
    request: Request,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Mint `count` single-use invitations and answer the links that ARE them.

    They are handed over by hand: expiring, bound to no address, and whoever redeems one
    chooses their own username — which is why a link must not be left where its holder
    was not meant to be. An administrator session is not a licence to mint credentials
    without limit, hence the throttle, which a batch pays link by link. `invite` and `link`
    repeat the first of the batch for a bundle that predates batches.
    """
    if not 1 <= body.count <= environment.INVITE_BATCH_MAX:
        raise HTTPException(
            422,
            f"Se pueden crear entre 1 y {environment.INVITE_BATCH_MAX} invitaciones a la vez.",
        )
    throttle("invite", request, admin.username, cost=body.count)
    terms = _terms(db, body)
    try:
        labels = queries.batch_labels(db, terms.label, body.count)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    minted = []
    for label in labels:
        invite, token = links.mint(
            db,
            expires_at=terms.expires_at,
            workspace_id=terms.workspace.id if terms.workspace else None,
            role=terms.role,
            created_by=admin.id,
            label=label,
            features=terms.features,
            profile=terms.profile,
        )
        minted.append(_minted(db, request, invite, token))
    logger.info(
        "[invitaciones] {} ha creado {} invitación(es) · {}",
        admin.username,
        len(minted),
        terms.workspace.slug if terms.workspace else "sin asignatura",
    )
    return {"invites": minted, "invite": minted[0]["invite"], "link": minted[0]["link"]}


@router.post("/invites/import")
def import_invite(
    body: InviteImportBody,
    request: Request,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Make a link somebody already holds work again, under the terms sent.

    For the invitation deleted by mistake: the link is still in somebody's hands, and
    reviving it is kinder than asking them to wait for another. Only a link nobody knows
    creates anything. One that still names an invitation of the list changes nothing about
    it — the list is where terms are edited — except that its link becomes showable if it
    was not; and one already used is refused, because an invitation serves once.
    """
    token = links.token_from(body.link)
    error = links.shape_error(token)
    if error:
        raise HTTPException(422, error)
    throttle("invite", request, admin.username)
    terms = _terms(db, body)

    existing = queries.invite_by_digest(db, auth.digest(token))
    if existing is not None:
        if existing.used_at is not None:
            raise HTTPException(
                409, "Ese enlace ya se usó y una invitación sirve una sola vez. Crea otra."
            )
        outcome = "unchanged"
        if links.unseal(existing.token_sealed, existing.token_hash) is None:
            sealed = links.seal(token)
            if sealed is not None:
                queries.edit_invite(db, existing, token_sealed=sealed)
                outcome = "recovered"
        logger.info(
            "[invitaciones] {} ha pegado el enlace de la invitación {} ({})",
            admin.username,
            existing.id,
            outcome,
        )
        return {"outcome": outcome, **_minted(db, request, existing, token)}

    invite, _ = links.mint(
        db,
        token=token,
        expires_at=terms.expires_at,
        workspace_id=terms.workspace.id if terms.workspace else None,
        role=terms.role,
        created_by=admin.id,
        label=terms.label,
        features=terms.features,
        profile=terms.profile,
    )
    logger.info("[invitaciones] {} ha recuperado un enlace como invitación {}", admin.username, invite.id)
    return {"outcome": "created", **_minted(db, request, invite, token)}


@router.get("/invites/{invite_id}/link")
def invite_link(
    invite_id: int,
    request: Request,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer an invitation's link again, and leave a line saying who read it.

    The one read in this router that hands out a credential, so it is a request of its own
    rather than a field of the listing: the list can stay on screen for an hour without a
    single live link sitting in the browser's cache.
    """
    invite = _unused_invite(db, invite_id)
    if invite.token_sealed is None:
        raise HTTPException(
            409,
            "El enlace de esta invitación no se guardó: es anterior a que Variatio guardara los "
            "enlaces. Si lo tienes, pégalo en «Recuperar un enlace»; si no, anúlala y crea otra.",
        )
    token = links.unseal(invite.token_sealed, invite.token_hash)
    if token is None:
        raise HTTPException(
            409,
            "No se puede abrir el enlace guardado: la clave con la que se cifró ya no está. El "
            "enlace sigue valiendo; si lo tienes, pégalo en «Recuperar un enlace».",
        )
    logger.info("[invitaciones] {} ha consultado el enlace de la invitación {}", admin.username, invite.id)
    return {"link": _link(request, token)}


@router.patch("/invites/{invite_id}")
def edit_invite(
    invite_id: int,
    body: InviteEditBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Change the terms of an invitation nobody has used yet.

    Moving the date is what brings an expired invitation back: the token did not change, so
    the link its holder already has works again. The holder sees the new asignatura and
    permission on opening it; the alias they never see.
    """
    invite = _unused_invite(db, invite_id)
    sent = body.model_fields_set
    changes: dict = {}
    if "label" in sent:
        changes["label"] = _label(body.label)
    if "expires_at" in sent:
        if body.expires_at is None:
            raise HTTPException(422, "Una invitación siempre tiene fecha de caducidad.")
        changes["expires_at"] = _expiry(body.expires_at)
    if "role" in sent:
        changes["role"] = _role(body.role)
    if "workspace" in sent:
        workspace = _workspace(db, body.workspace)
        changes["workspace_id"] = workspace.id if workspace else None
    if "features" in sent:
        changes["features"] = _features(body.features)
    if "profile" in sent:
        changes["profile"] = _profile(body.profile)
    queries.edit_invite(db, invite, **changes)
    if changes:
        logger.info(
            "[invitaciones] {} ha cambiado la invitación {}: {}",
            admin.username,
            invite.id,
            ", ".join(sorted(sent)),
        )
    return {"invite": _invite(db, invite)}


@router.delete("/invites/{invite_id}")
def revoke_invite(
    invite_id: int,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Withdraw an invitation before anybody redeems it: its link stops working at once."""
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe.")
    revoked = queries.revoke_invite(db, invite_id)
    if revoked:
        logger.info("[invitaciones] {} ha anulado la invitación {}", admin.username, invite_id)
    return {"revoked": revoked}


@dataclass(frozen=True)
class _Terms:
    """An invitation's terms once every one of them has been checked."""

    workspace: Workspace | None
    role: str
    expires_at: datetime
    label: str | None
    features: list[str]
    profile: str


def _terms(db: DbSession, body: InviteTerms) -> _Terms:
    """Check what a new invitation is to grant, refusing in the order the form asks it."""
    return _Terms(
        workspace=_workspace(db, body.workspace),
        role=_role(body.role),
        expires_at=_expiry(body.expires_at),
        label=_label(body.label),
        features=_features(body.features),
        profile=_profile(body.profile),
    )


def _workspace(db: DbSession, slug: str | None) -> Workspace | None:
    """Resolve the asignatura an invitation lets into, or None for none."""
    if not slug:
        return None
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    return workspace


def _role(role: str | None) -> str:
    """Accept one of the three roles and nothing else."""
    if role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{role}'. Usa uno de {', '.join(ROLES)}.")
    return role


def _profile(profile: str | None) -> str:
    """Accept what the account an invitation creates will be: a teacher or a student."""
    error = queries.profile_error(profile)
    if error:
        raise HTTPException(422, error)
    return profile


def _features(names: list[str] | None) -> list[str]:
    """Accept the optional functions an invitation lists its holder for, each once."""
    names = list(dict.fromkeys(names or []))
    unknown = features.unknown(names)
    if unknown:
        raise HTTPException(
            422,
            f"Función desconocida: {', '.join(unknown)}. Usa de {', '.join(features.FEATURES)}.",
        )
    return names


def _expiry(value: datetime | None) -> datetime:
    """Resolve when an invitation stops working: the default week, or a moment still ahead.

    A moment with no zone is read as UTC. The clock may be naive too — SQLite in the test
    suite keeps no offset — and then the moment is compared, and stored, as naive UTC.
    """
    moment = queries.now()
    if value is None:
        return moment + environment.INVITE_TTL
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if moment.tzinfo is None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value <= moment:
        raise HTTPException(422, "Esa fecha de caducidad ya ha pasado: elige una que esté por llegar.")
    return value


def _label(label: str | None) -> str | None:
    """Fold an alias to what is stored, refusing one that does not fit."""
    label = queries.normalise_label(label)
    error = queries.label_error(label)
    if error:
        raise HTTPException(422, error)
    return label


def _unused_invite(db: DbSession, invite_id: int) -> Invite:
    """Return an invitation that can still be read and changed: it exists and nobody used it."""
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe.")
    if invite.used_at is not None:
        raise HTTPException(409, "Esa invitación ya se usó: ya no se puede cambiar ni volver a ver.")
    return invite


def _minted(db: DbSession, request: Request, invite: Invite, token: str) -> dict:
    """Render an invitation just handed over: the row, its link, and whether it was kept."""
    return {
        "invite": _invite(db, invite),
        "link": _link(request, token),
        "stored": invite.token_sealed is not None,
    }


def _link(request: Request, token: str) -> str:
    """Build the link that IS an invitation."""
    return links.url_for(auth.base_url(request), token)


def _invite(db: DbSession, invite: Invite, moment: datetime | None = None) -> dict:
    """Render one invitation for the panel. Never its token, sealed or not — that is `/link`."""
    workspace = invite.workspace
    author = queries.get_user_by_id(db, invite.created_by) if invite.created_by else None
    moment = moment if moment is not None else queries.now()
    return {
        "id": invite.id,
        "label": invite.label,
        "role": invite.role,
        "features": list(invite.features or []),
        "profile": invite.profile,
        "workspace": workspace.name if workspace else None,
        "workspace_slug": workspace.slug if workspace else None,
        "created_at": invite.created_at.isoformat(),
        "expires_at": invite.expires_at.isoformat(),
        "created_by": author.username if author else None,
        "state": "pending" if invite.expires_at > moment else "expired",
        "link_stored": invite.token_sealed is not None,
    }
