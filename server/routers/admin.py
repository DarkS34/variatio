"""The installation's own panel: the accounts, the workspaces and how the evaluation is going.

Every route here is behind `require_admin`, and the whole router exists under `/api/admin`
because `/api/workspaces`'s `auth.MANAGE` only ever reaches the ACTIVE workspace — tidying
up the installation from there would mean entering each instance in order to touch it.

INVITATIONS AND MEMBERSHIP ARE THE INSTALLATION ADMINISTRATOR'S ALONE. There is no
owner-scoped door: an owner owns their workspace's content and does not decide who else
exists. Two screens for one question is how an installation ends up with two answers.

What this is NOT: a second way into the pipeline. Nothing here builds, edits or approves
anything. It reads what the installation has recorded, hands out access, and exports a CSV.
It reads across accounts twice: the evaluation — whose unit of analysis is a session, and
whose interesting question cannot be answered from inside one account — and the exercises
generated in each workspace, read-only, which no other route shows anybody but their author.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from evaluation.api import store as evaluation_store

from .. import approvals, auth, deps, features, installation, maintenance, members, singletons, storage
from .. import generations as generations_store
from ..auth import deps as auth_deps
from ..auth import links
from ..auth.rate_limit import locked_seconds, throttle, unlock
from ..db import identity, repository
from ..db.models import EDITOR, ROLES, TEACHER, VIA_ADMIN, ClassLink, Invite, User, Workspace
from ..editors import profile_edit
from ..jobs import lanes as jobs_lanes
from .generations import row_view

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)

# What a refused profile change carries in `X-Error-Code`: the profile only climbs.
PROFILE_ONLY_CLIMBS = "profile_only_climbs"


class InviteTerms(BaseModel):
    """What an invitation grants, until when, and the name only the panel ever reads.

    `workspace` may be absent — an invitation granting no membership creates an account
    and no access, which is the honest way to add somebody who will be given a workspace
    later. `features` lists the new account for the optional functions named
    (`server/features.py`), which is access too. `profile` is what the account will be, a
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


class ClassLinkEditBody(BaseModel):
    """Whether a subject's class link is paused, from the panel."""

    paused: bool


class MembershipBody(BaseModel):
    """The instance somebody is being let into, and with what role."""

    workspace: str
    role: str = EDITOR


class AdminBody(BaseModel):
    """Whether this account runs the installation."""

    is_admin: bool


class ProfileBody(BaseModel):
    """The profile an account is raised to, which can only be `teacher`."""

    evaluator_profile: str | None = None


class FeatureBody(BaseModel):
    """Who one optional function is for: its mode and, when sent, its accounts and subjects."""

    mode: str
    accounts: list[int] | None = None
    workspaces: list[str] | None = None


class MaintenanceBody(BaseModel):
    """Whether the door is shut, and the notice shown while it is."""

    active: bool
    message: str | None = None


# WHO AND WHAT ----------------------------------------------------------------------------


def _lane_jobs() -> dict:
    """Report what is holding each lane, as a list and with the room it is filling.

    A list per lane and not one job: the remote lane holds as many as
    `CEREBRAS_MAX_CONCURRENT_JOBS` allows, so the oldest of them does not answer "what is
    this half of the engine doing", and N jobs means nothing without the capacity.
    """
    return {
        backend: {
            "capacity": jobs_lanes.capacity(backend),
            "jobs": [job.to_dict() for job in singletons.runner.holders_in(backend)],
        }
        for backend in jobs_lanes.BACKENDS
    }


def _account_view(db: DbSession, user: User, generated: dict, by_account: dict) -> dict:
    """Render one account for the panel: what it is, what it holds and what it produced."""
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "is_admin": user.is_admin,
        "evaluator_profile": user.evaluator_profile,
        "disabled": not user.active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "workspaces": [
            {"slug": w.slug, "role": m.role, "disabled": not m.active}
            for m, w in identity.memberships_for(db, user.id, include_disabled=True)
        ],
        "generations": generated.get(user.id, 0),
        "evaluations": by_account.get(user.id, {}).get("sessions", 0),
        "decided": by_account.get(user.id, {}).get("decided", 0),
        "sessions": identity.count_live_sessions(db, user.id),
        "locked_seconds": locked_seconds("login", user.username),
        "email": user.email,
    }


def _workspace_view(db: DbSession, workspace) -> dict:
    """Render one instance for the panel, chain included.

    `stages` reads three files per workspace so a stage can be emptied from here without
    switching to it. It does not mount the instance's index.
    """
    return {
        "id": workspace.id,
        "slug": workspace.slug,
        "name": workspace.name,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "members": len(identity.members_of(db, workspace.id)),
        # Who owns it and how many study in it: a subject with nobody to own it is the one
        # thing on this row that asks for the administrator («Elegir propietario»).
        "owners": [
            {"id": user.id, "username": user.username, "name": user.name}
            for user in members.owners_of(db, workspace)
        ],
        "people": members.people_of(db, workspace),
        "generations": generations_store.count(installation.workspace_for(workspace.slug)),
        "warm": workspace.slug in deps.warm_slugs(),
        "stages": _chain(workspace.slug),
        "disk": installation.disk_usage(installation.workspace_for(workspace.slug)),
    }


@router.get("/overview")
def overview(db: DbSession = Depends(auth.db)) -> dict:
    """Answer the whole panel: totals, every account, every instance and the queue."""
    workspaces = repository.list_workspaces(db)
    users = identity.list_users(db)
    trees = [installation.workspace_for(workspace.slug) for workspace in workspaces]
    generated = generations_store.count_by_author(trees)
    headers = evaluation_store.headers(db)
    by_account = {group["key"]: group for group in evaluation_store.by_account(headers)}

    running = singletons.runner.running()
    return {
        "totals": {
            "users": len(users),
            "workspaces": len(workspaces),
            "generations": sum(generations_store.count(ws) for ws in trees),
            "evaluations": len(headers),
            "decided": sum(1 for h in headers if h.get("chosen_at")),
        },
        "accounts": [
            _account_view(db, user, generated, by_account) for user in users
        ],
        "workspaces": [_workspace_view(db, workspace) for workspace in workspaces],
        "engine": {
            "busy": bool(running),
            "job": running[0].to_dict() if running else None,
            "lanes": _lane_jobs(),
            "queued": len(singletons.runner.pending()),
            "warm_contexts": deps.warm_slugs(),
        },
    }


# ACCESS ----------------------------------------------------------------------------------
#
# The only way an account comes into existence, and the only way one enters a workspace.


@router.get("/invites")
def invites(db: DbSession = Depends(auth.db)) -> dict:
    """List every invitation nobody has used yet, live and expired alike.

    Expired ones stay because a date can be moved, and the same link works again once it
    is. What a row never carries is its link: that is a request of its own, and a logged one.
    """
    moment = identity.now()
    return {"invites": [_invite(db, row, moment) for row in identity.unused_invites(db)]}


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
    if not 1 <= body.count <= installation.INVITE_BATCH_MAX:
        raise HTTPException(
            422,
            f"Se pueden crear entre 1 y {installation.INVITE_BATCH_MAX} invitaciones a la vez.",
        )
    throttle("invite", request, admin.username, cost=body.count)
    terms = _terms(db, body)
    try:
        labels = identity.batch_labels(db, terms.label, body.count)
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

    existing = identity.invite_by_digest(db, auth.digest(token))
    if existing is not None:
        if existing.used_at is not None:
            raise HTTPException(
                409, "Ese enlace ya se usó y una invitación sirve una sola vez. Crea otra."
            )
        outcome = "unchanged"
        if links.unseal(existing.token_sealed, existing.token_hash) is None:
            sealed = links.seal(token)
            if sealed is not None:
                identity.edit_invite(db, existing, token_sealed=sealed)
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
    identity.edit_invite(db, invite, **changes)
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
    revoked = identity.revoke_invite(db, invite_id)
    if revoked:
        logger.info("[invitaciones] {} ha anulado la invitación {}", admin.username, invite_id)
    return {"revoked": revoked}


# CLASS LINKS -----------------------------------------------------------------------------
#
# Each subject's live class link, its teachers' to mint: the administrator sees how full each
# is and can pause or retire one — a link that reached somewhere it should not have.


@router.get("/class-links")
def class_links(db: DbSession = Depends(auth.db)) -> dict:
    """List every live class link: its subject, seats, expiry, pause and who minted it."""
    moment = identity.now()
    return {"class_links": [_class_link(db, link, moment) for link in identity.class_links(db)]}


@router.patch("/class-links/{link_id}")
def pause_class_link(
    link_id: int,
    body: ClassLinkEditBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Pause a subject's class link, or resume it."""
    link = _live_class_link(db, link_id)
    identity.edit_class_link(db, link, paused_at=identity.now() if body.paused else None)
    logger.info(
        "[invitaciones] {} ha {} el enlace de clase de «{}»",
        admin.username,
        "pausado" if body.paused else "reanudado",
        link.workspace.slug,
    )
    return {"id": link.id, "paused": body.paused}


@router.delete("/class-links/{link_id}")
def revoke_class_link(
    link_id: int,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Retire a subject's class link: it stops working, and whoever entered through it stays."""
    link = _live_class_link(db, link_id)
    identity.revoke_class_link(db, link)
    logger.info("[invitaciones] {} ha retirado el enlace de clase de «{}»", admin.username, link.workspace.slug)
    return {"revoked": link.id}


@router.post("/accounts/{user_id}/memberships")
def grant_membership(
    user_id: int, body: MembershipBody, db: DbSession = Depends(auth.db)
) -> dict:
    """Let one account into one instance, with a role."""
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'.")
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    workspace = repository.get_workspace(db, body.workspace)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{body.workspace}'.")

    if identity.membership(db, workspace.id, user.id) is None:
        identity.grant(db, workspace.id, user.id, body.role, via=VIA_ADMIN)
    else:
        try:
            members.change_role(db, workspace, user, body.role)
        except members.Refusal as refusal:
            raise _refused(refusal) from None
    return {"user_id": user.id, "workspace": workspace.slug, "role": body.role}


@router.post("/accounts/{user_id}/profile")
def set_profile(user_id: int, body: ProfileBody, db: DbSession = Depends(auth.db)) -> dict:
    """Make an account a teacher. The profile only climbs: nothing lowers a teacher.

    A teacher creates subjects and may have created some already, so lowering one would
    leave them owning what their profile no longer lets them make; and a student who is to
    teach is raised here, never by their own answer. Anything but `teacher` — a student,
    nothing, a word nobody knows — is refused with `profile_only_climbs`. Raising a teacher
    changes nothing and is not an error.
    """
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if body.evaluator_profile != TEACHER:
        raise HTTPException(
            409,
            "El perfil de una cuenta solo sube, de alumno a docente: no se puede bajar ni quitar.",
            headers={"X-Error-Code": PROFILE_ONLY_CLIMBS},
        )
    if user.evaluator_profile != TEACHER:
        identity.set_evaluator_profile(db, user, TEACHER)
        logger.info("[cuentas] «{}» pasa a ser docente", user.username)
    return {"user_id": user.id, "evaluator_profile": user.evaluator_profile}


@router.delete("/accounts/{user_id}/memberships/{slug}")
def revoke_membership(
    user_id: int,
    slug: str,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Take one account's access to one instance away, as a teacher's removal does.

    The same gesture (`members.remove_member`): the account leaves the subject, its jobs there
    stop and an open socket closes; the subject's last active owner is refused (`last_owner`).
    A membership that does not exist is nothing to take away, and not an error.
    """
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    user = identity.get_user_by_id(db, user_id)
    if user is not None and identity.membership(db, workspace.id, user.id) is not None:
        try:
            members.remove_member(db, workspace, user, admin)
        except members.Refusal as refusal:
            raise _refused(refusal) from None
    return {"user_id": user_id, "workspace": slug}


@router.post("/accounts/{user_id}/memberships/{slug}/enable")
def enable_membership(
    user_id: int,
    slug: str,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Open again one account's access a teacher paused, as the teacher's own «Activar» does."""
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    user = identity.get_user_by_id(db, user_id)
    if user is None or identity.membership(db, workspace.id, user.id) is None:
        raise HTTPException(404, "Esa cuenta no está en esa asignatura.")
    try:
        members.enable_member(db, workspace, user, admin)
    except members.Refusal as refusal:
        raise _refused(refusal) from None
    return {"user_id": user_id, "workspace": slug}


# WORKSPACES ------------------------------------------------------------------------------
#
# What this panel writes about instances: their name and their removal. It builds, edits
# and approves nothing.


class RenameBody(BaseModel):
    """A workspace's new display name."""

    name: str = Field(min_length=1, max_length=200)


@router.patch("/workspaces/{slug}")
def rename_workspace(slug: str, body: RenameBody, db: DbSession = Depends(auth.db)) -> dict:
    """Rename one instance. The only door — there is no owner-scoped route for it.

    Only the NAME changes: the slug names the directory tree, the `X-Workspace` header
    and every row that points at the workspace, so renaming that would be a migration.
    """
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    workspace.name = body.name.strip()
    db.flush()
    logger.info(f"[admin] Asignatura '{slug}' renombrada a «{workspace.name}»")
    return {"slug": slug, "name": workspace.name}


@router.delete("/workspaces/{slug}")
def delete_workspace(
    slug: str,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Delete one instance and its directory tree, whoever else is a member of it.

    Unconditional, unlike `DELETE /api/workspaces/{slug}`, which keeps the files when
    other people are still in it: this is the installation being tidied up, and an
    administrator is who finishes the job the other door leaves half done.

    There is deliberately NO "last workspace of the installation" guard: an installation
    holding zero workspaces is a normal state the app renders on purpose, and `leave`
    already deletes the last one when its last member walks out.
    """
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    ws = installation.workspace_for(slug)
    # Tree before row: this way a failure leaves the row standing and the call retryable,
    # where the other order strands files nobody is on record as owning.
    try:
        removed = installation.destroy(ws)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, f"No se pudo borrar '{ws.root}': {exc}") from exc

    # Whoever was sitting in it is moved before the row goes: a dangling pointer leaves
    # them holding a slug the API answers 404 for, with the switcher offering no way back.
    rehomed = auth_deps.rehome_accounts(db, workspace)

    db.delete(workspace)
    db.flush()
    deps.invalidate(slug, "workspace eliminado")
    # Heard only by whoever is looking at the instance that has just stopped existing,
    # which is exactly who has to reload.
    singletons.bus.publish(slug, None, "workspace.deleted", {"slug": slug})
    return {
        "deleted": slug,
        "path": str(ws.root),
        "files_removed": removed,
        "rehomed": rehomed,
        # Where the caller ends up: the one entry of `rehomed` the calling tab needs. It is
        # `None` both when they were not in it and when they have nowhere left to go, two
        # states the panel draws the same way — it stays put.
        "landed": rehomed.get(admin.username),
    }


class EndCourseBody(BaseModel):
    """How a course ends: its students paused (`disable`, undone by opening them) or removed."""

    action: str = "disable"


@router.post("/workspaces/{slug}/end-course")
def end_course(
    slug: str,
    body: EndCourseBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """End one subject's course: every active student paused, or removed, and the link paused.

    The administrator's alone (the user's decision, 2026-10-07: the owner's button at the foot
    of «Clase» was taken away). The teachers and the files stay (`members.end_course`).
    """
    if body.action not in ("disable", "remove"):
        raise HTTPException(422, f"Fin de curso desconocido: '{body.action}'.")
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    answer = members.end_course(db, workspace, admin, body.action)
    logger.info(
        "[admin] «{}» terminó el curso de «{}»: {} alumno(s) {}",
        admin.username,
        slug,
        answer["students"],
        "desactivado(s)" if body.action == "disable" else "quitado(s)",
    )
    return answer


@router.delete("/workspaces/{slug}/artifacts/{artifact}")
def delete_artifact(slug: str, artifact: str, db: DbSession = Depends(auth.db)) -> dict:
    """Empty one stage, leaving the workspace standing and the artifact "missing".

    What goes is the curated file, the draft and the cache derivations that spoke of it,
    which is what allows rebuilding. `.history/` is untouched, so a mistaken deletion is
    undone from "Restaurar" on the artifact's own screen — and that is what makes this
    button safe to offer at all.
    """
    if artifact not in approvals.ARTIFACTS:
        raise HTTPException(404, f"Artefacto desconocido: '{artifact}'.")
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    if artifact in singletons.runner.building_artifacts(slug):
        raise HTTPException(
            409, "Ese artefacto se está construyendo ahora mismo; cancela el trabajo antes."
        )

    ws = installation.workspace_for(slug)
    result = approvals.discard(ws, artifact)
    deps.invalidate(slug, f"'{artifact}' eliminado desde administración")
    singletons.bus.publish(slug, None, "pipeline.changed", {"artifact": artifact, "action": "discard"})
    return {"workspace": slug, **result}


@router.delete("/workspaces/{slug}/cache")
def clear_cache(slug: str, db: DbSession = Depends(auth.db)) -> dict:
    """Drop the regenerable half of a cache: the vectors and the converted markdown.

    The descriptions and the concept sources stay — they cost a model run. Refused while
    the workspace has work running or waiting, because that work reads these files.
    """
    if repository.get_workspace(db, slug) is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    # Every run of this workspace, on either lane: `current()` alone would miss the one on
    # the second lane whenever somebody else's older job holds the first.
    if singletons.runner.running(slug) or singletons.runner.pending(slug):
        raise HTTPException(409, "Esa asignatura tiene trabajo en curso o en cola; espera o cancélalo.")
    ws = installation.workspace_for(slug)
    result = installation.clear_cache(ws)
    deps.invalidate(slug, "caché vaciada desde administración")
    return {"workspace": slug, **result}


@router.get("/workspaces/{slug}/generations")
def workspace_generations(
    slug: str,
    author: int | None = None,
    q: str | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer one page of every exercise generated in this workspace, whoever wrote it.

    Read-only: nothing here promotes or deletes, which stay the author's. It carries the
    workspace's profile because the rows are drawn with it and the administrator need not
    be a member. `authors` lists every account with exercises here, for the filter.
    """
    if repository.get_workspace(db, slug) is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    ws = installation.workspace_for(slug)
    accounts = {user.id: user for user in identity.list_users(db)}
    pairs, total = generations_store.list_all(
        ws, author=author, query=q, limit=limit, offset=offset
    )
    return {
        "workspace": slug,
        "generations": [row_view(record, accounts.get(user_id)) for user_id, record in pairs],
        "total": total,
        "limit": limit,
        "offset": offset,
        "authors": [
            {
                "id": user_id,
                "username": accounts[user_id].username,
                "name": accounts[user_id].name,
            }
            for user_id in generations_store.authors(ws)
            if user_id is not None and user_id in accounts
        ],
        "profile": profile_edit.load(ws).get("profile"),
    }


@router.get("/workspaces/{slug}/export")
def export_workspace(slug: str, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the instance as the FILES say it is: what a checkout needs to run it.

    Read from disk and not from the database rows, because the files are the operational
    truth and the rows are their mirror.
    """
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")
    ws = installation.workspace_for(slug)
    files = {
        "knowledge_graph": ws.kg_path,
        "knowledge_graph_autogenerated": ws.kg_autogenerated_path,
        "exemplars_profile": ws.exemplars_profile_path,
        "exemplars_profile_autogenerated": ws.exemplars_profile_autogenerated_path,
        "exemplars_bank": ws.exemplars_bank_path,
        "content_context": ws.content_context_path,
        "content_context_autogenerated": ws.content_context_autogenerated_path,
        "review_state": ws.review_state_path,
        "curriculum": ws.curriculum_path,
    }
    return {
        "workspace": slug,
        "name": workspace.name,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "files": {key: storage.read_json(path) for key, path in files.items() if path.is_file()},
    }


# THE QUEUE -------------------------------------------------------------------------------


@router.get("/jobs")
def job_queue() -> dict:
    """Answer the queue of the whole installation, lane by lane.

    `running` is the oldest job, kept as it was; `lanes` is the honest picture now that
    the queue serialises per backend and two jobs can be in flight at once.
    """
    running = singletons.runner.running()
    return {
        "running": running[0].to_dict() if running else None,
        "lanes": _lane_jobs(),
        "queued": [
            {**job.to_dict(), "queue_position": singletons.runner.queue_position(job.id)}
            for job in singletons.runner.pending()
        ],
    }


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str) -> dict:
    """Cancel any job of the installation, whatever workspace it belongs to."""
    if singletons.runner.get(job_id) is None:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'.")
    return {"cancelled": singletons.runner.cancel(job_id)}


# ACCOUNTS --------------------------------------------------------------------------------


@router.post("/accounts/{user_id}/disable")
def disable(
    user_id: int, admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
    """Shut the door on one account, revoking its sessions, without deleting anything."""
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id:
        raise HTTPException(409, "No puedes desactivar tu propia cuenta.")
    user.disabled_at = identity.now()
    identity.revoke_all_sessions(db, user.id)
    return {"disabled": user_id}


@router.post("/accounts/{user_id}/enable")
def enable(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    """Let a disabled account back in."""
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    user.disabled_at = None
    return {"enabled": user_id}


@router.delete("/accounts/{user_id}")
def delete_account(
    user_id: int, admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
    """Delete one account. What it produced survives it.

    Deliberately not `disable`: that keeps the account and shuts the door, this removes
    the account and leaves standing what it made — its generated exercises stay in their
    directory of the workspace, which nobody reads any more, and `evaluation_sessions.user_id`
    is `SET NULL`, so deleting somebody must not delete the material a course was built on. Deleting yourself is refused, which is also what keeps
    the installation from losing its last administrator.
    """
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id:
        raise HTTPException(409, "No puedes borrar tu propia cuenta.")

    username = user.username
    identity.delete_user(db, user)
    return {"deleted": user_id, "username": username}


@router.post("/accounts/{user_id}/admin")
def set_admin(
    user_id: int,
    body: AdminBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Grant or withdraw administration, never from oneself.

    A flag on the account; the bypass it buys lives in one `if`, `auth.deps.access_for`.
    Taking it from yourself is refused for the same reason deleting yourself is. An
    administrator is a teacher: granting it raises the profile, which only climbs, so
    withdrawing it leaves the teacher a teacher.
    """
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id and not body.is_admin:
        raise HTTPException(409, "No puedes quitarte la administración a ti mismo.")
    user.is_admin = body.is_admin
    if user.is_admin and user.evaluator_profile != TEACHER:
        user.evaluator_profile = TEACHER
    db.flush()
    return {"user_id": user.id, "is_admin": user.is_admin}


@router.post("/accounts/{user_id}/reset-link")
def reset_link(user_id: int, request: Request, db: DbSession = Depends(auth.db)) -> dict:
    """Issue the same link `/forgot` would mail, handed over by hand instead.

    With no SMTP the only route to a locked-out person is by hand, and this is where the
    administrator already is. It is issued, not sent, and it expires like any other.
    """
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if not user.active:
        raise HTTPException(409, "La cuenta está desactivada: reactívala antes.")
    token = auth.new_token()
    identity.create_reset(db, user.id, auth.digest(token), installation.RESET_TTL)
    return {
        "user_id": user.id,
        "link": f"{auth.base_url(request)}/reset?token={token}",
        "expires_in_minutes": int(installation.RESET_TTL.total_seconds() // 60),
    }


@router.delete("/accounts/{user_id}/sessions")
def revoke_sessions(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    """Log one account out everywhere without touching the account itself."""
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    return {"user_id": user.id, "revoked": identity.revoke_all_sessions(db, user.id)}


@router.post("/accounts/{user_id}/unlock")
def unlock_login(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    """Clear the login rate limiter for one account. Its key only, never the IP's."""
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    unlock("login", user.username)
    return {"user_id": user.id, "unlocked": True}


# THE DOOR --------------------------------------------------------------------------------


@router.get("/maintenance")
def read_maintenance() -> dict:
    """Answer the door's state with who closed it, which the public route withholds."""
    return maintenance.state()


@router.post("/maintenance")
def set_maintenance(
    body: MaintenanceBody, admin: User = Depends(auth.require_admin)
) -> dict:
    """Open or shut the installation. Written here and nowhere else.

    Reading it does NOT go through here: `GET /api/maintenance` asks for no session,
    because the notice has to reach whoever has not got in yet.
    """
    return maintenance.set_state(body.active, body.message, admin.username)


@router.get("/features")
def read_features(db: DbSession = Depends(auth.db)) -> dict:
    """Answer who each optional function is for: its mode and the accounts on its list."""
    return {"features": features.snapshot(db)}


@router.put("/features/{feature}")
def set_feature(
    feature: str,
    body: FeatureBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Set who one optional function is for.

    A list is replaced only when it is sent — `accounts`, or `workspaces` for a function a
    subject may be listed for — so switching the mode alone keeps both.
    """
    if feature not in features.FEATURES:
        raise HTTPException(404, f"No existe la función '{feature}'.")
    if body.mode not in features.MODES:
        raise HTTPException(
            422, f"Modo desconocido: '{body.mode}'. Usa uno de {', '.join(features.MODES)}."
        )
    if body.accounts is not None:
        missing = [uid for uid in body.accounts if identity.get_user_by_id(db, uid) is None]
        if missing:
            raise HTTPException(
                422, f"No existe la cuenta {', '.join(str(uid) for uid in missing)}."
            )
        features.set_listed(db, feature, body.accounts)
    if body.workspaces is not None:
        if feature not in features.SUBJECT_LISTED:
            raise HTTPException(
                422, "Esta función se abre cuenta por cuenta, no por asignaturas."
            )
        rows = {slug: repository.get_workspace(db, slug) for slug in dict.fromkeys(body.workspaces)}
        missing = [slug for slug, row in rows.items() if row is None]
        if missing:
            raise HTTPException(422, f"No existe la asignatura {', '.join(missing)}.")
        features.set_listed_subjects(db, feature, [row.id for row in rows.values()])
    features.set_mode(db, feature, body.mode)
    logger.info(
        "[funciones] {} ha puesto '{}' en modo '{}' · {} cuenta(s) y {} asignatura(s) en la lista",
        admin.username,
        feature,
        body.mode,
        len(features.listed(db, feature)),
        len(features.listed_subjects(db, feature)) if feature in features.SUBJECT_LISTED else 0,
    )
    return {"features": features.snapshot(db)}


# HELPERS ---------------------------------------------------------------------------------


def _chain(slug: str) -> list[dict]:
    """Read one workspace's three stages from its files, without mounting its index."""
    ws = installation.workspace_for(slug)
    return [
        {
            "artifact": stage["artifact"],
            "label": stage["label"],
            "status": stage["status"],
            "is_autogenerated": stage["is_autogenerated"],
        }
        for stage in singletons.pipeline_snapshot(ws)
    ]


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


def _class_link(db: DbSession, link: ClassLink, moment: datetime) -> dict:
    """Render a class link for the panel: its subject, how full it is, and who minted it."""
    author = identity.get_user_by_id(db, link.created_by) if link.created_by else None
    return {
        "id": link.id,
        "workspace": link.workspace.slug,
        "workspace_name": link.workspace.name,
        "uses": link.uses,
        "max_uses": link.max_uses,
        "expires_at": link.expires_at.isoformat(),
        "expired": link.expires_at <= moment,
        "paused": link.paused_at is not None,
        "created_by": author.username if author else None,
    }


def _live_class_link(db: DbSession, link_id: int) -> ClassLink:
    """Return a class link that has not been retired, or 404."""
    link = db.get(ClassLink, link_id)
    if link is None or link.revoked_at is not None:
        raise HTTPException(404, "Ese enlace de clase no existe.")
    return link


def _refused(refusal: members.Refusal) -> HTTPException:
    """Turn a refused membership gesture into the answer the panel reads by its code."""
    return HTTPException(refusal.status, refusal.message, headers={"X-Error-Code": refusal.code})


def _profile(profile: str | None) -> str:
    """Accept what the account an invitation creates will be: a teacher or a student."""
    error = identity.profile_error(profile)
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
    moment = identity.now()
    if value is None:
        return moment + installation.INVITE_TTL
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if moment.tzinfo is None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value <= moment:
        raise HTTPException(422, "Esa fecha de caducidad ya ha pasado: elige una que esté por llegar.")
    return value


def _label(label: str | None) -> str | None:
    """Fold an alias to what is stored, refusing one that does not fit."""
    label = identity.normalise_label(label)
    error = identity.label_error(label)
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
    author = identity.get_user_by_id(db, invite.created_by) if invite.created_by else None
    moment = moment if moment is not None else identity.now()
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
