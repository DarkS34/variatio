"""The panel's accounts and its front page: every account, subject and lane at a glance.

Every route here is behind `require_admin`, under `/api/admin` like every route of the panel,
whose other tabs are the modules beside this one. INVITATIONS AND MEMBERSHIP ARE THE
INSTALLATION ADMINISTRATOR'S ALONE: the invitations are `invites.py`, and an account's
memberships are granted, paused and revoked here.

What the panel is NOT: a second way into the pipeline. Nothing in it builds, edits or approves
anything. It reads what the installation has recorded, hands out access, and exports a CSV.
It reads across accounts twice: the evaluation — whose unit of analysis is a session, and
whose interesting question cannot be answered from inside one account — and the exercises
generated in each workspace, read-only (`workspaces.py`).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from consumers.evaluation.api import store as evaluation_store

from .. import auth
from .. import generations as generations_store
from ..auth import queries
from ..auth.rate_limit import locked_seconds, unlock
from ..classroom import members
from ..core import contexts, environment, installation, process
from ..db import repository
from ..db.models import EDITOR, ROLES, TEACHER, VIA_ADMIN, User
from ..pipeline import readings
from ..workspaces import trees as workspaces_trees
from .shared import _lane_jobs

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)

# What a refused profile change carries in `X-Error-Code`: the profile only climbs.
PROFILE_ONLY_CLIMBS = "profile_only_climbs"


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


# WHO AND WHAT ----------------------------------------------------------------------------


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
            for m, w in queries.memberships_for(db, user.id, include_disabled=True)
        ],
        "generations": generated.get(user.id, 0),
        "evaluations": by_account.get(user.id, {}).get("sessions", 0),
        "decided": by_account.get(user.id, {}).get("decided", 0),
        "sessions": queries.count_live_sessions(db, user.id),
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
        "members": len(queries.members_of(db, workspace.id)),
        # Who owns it and how many study in it: a subject with nobody to own it is the one
        # thing on this row that asks for the administrator («Elegir propietario»).
        "owners": [
            {"id": user.id, "username": user.username, "name": user.name}
            for user in members.owners_of(db, workspace)
        ],
        "people": members.people_of(db, workspace),
        "generations": generations_store.count(installation.workspace_for(workspace.slug)),
        "warm": workspace.slug in contexts.warm_slugs(),
        "stages": _chain(workspace.slug),
        "disk": workspaces_trees.disk_usage(installation.workspace_for(workspace.slug)),
    }


@router.get("/overview")
def overview(db: DbSession = Depends(auth.db)) -> dict:
    """Answer the whole panel: totals, every account, every instance and the queue."""
    workspaces = repository.list_workspaces(db)
    users = queries.list_users(db)
    trees = [installation.workspace_for(workspace.slug) for workspace in workspaces]
    generated = generations_store.count_by_author(trees)
    headers = evaluation_store.headers(db)
    by_account = {group["key"]: group for group in evaluation_store.by_account(headers)}

    running = process.runner.running()
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
            "queued": len(process.runner.pending()),
            "warm_contexts": contexts.warm_slugs(),
        },
    }


@router.post("/accounts/{user_id}/memberships")
def grant_membership(
    user_id: int, body: MembershipBody, db: DbSession = Depends(auth.db)
) -> dict:
    """Let one account into one instance, with a role."""
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'.")
    user = queries.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    workspace = repository.get_workspace(db, body.workspace)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{body.workspace}'.")

    if queries.membership(db, workspace.id, user.id) is None:
        queries.grant(db, workspace.id, user.id, body.role, via=VIA_ADMIN)
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
    user = queries.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if body.evaluator_profile != TEACHER:
        raise HTTPException(
            409,
            "El perfil de una cuenta solo sube, de alumno a docente: no se puede bajar ni quitar.",
            headers={"X-Error-Code": PROFILE_ONLY_CLIMBS},
        )
    if user.evaluator_profile != TEACHER:
        queries.set_evaluator_profile(db, user, TEACHER)
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
    user = queries.get_user_by_id(db, user_id)
    if user is not None and queries.membership(db, workspace.id, user.id) is not None:
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
    user = queries.get_user_by_id(db, user_id)
    if user is None or queries.membership(db, workspace.id, user.id) is None:
        raise HTTPException(404, "Esa cuenta no está en esa asignatura.")
    try:
        members.enable_member(db, workspace, user, admin)
    except members.Refusal as refusal:
        raise _refused(refusal) from None
    return {"user_id": user_id, "workspace": slug}


# ACCOUNTS --------------------------------------------------------------------------------


@router.post("/accounts/{user_id}/disable")
def disable(
    user_id: int, admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
    """Shut the door on one account, revoking its sessions, without deleting anything."""
    user = queries.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id:
        raise HTTPException(409, "No puedes desactivar tu propia cuenta.")
    user.disabled_at = queries.now()
    queries.revoke_all_sessions(db, user.id)
    return {"disabled": user_id}


@router.post("/accounts/{user_id}/enable")
def enable(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    """Let a disabled account back in."""
    user = queries.get_user_by_id(db, user_id)
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
    user = queries.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id:
        raise HTTPException(409, "No puedes borrar tu propia cuenta.")

    username = user.username
    queries.delete_user(db, user)
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
    user = queries.get_user_by_id(db, user_id)
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
    user = queries.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if not user.active:
        raise HTTPException(409, "La cuenta está desactivada: reactívala antes.")
    token = auth.new_token()
    queries.create_reset(db, user.id, auth.digest(token), environment.RESET_TTL)
    return {
        "user_id": user.id,
        "link": f"{auth.base_url(request)}/reset?token={token}",
        "expires_in_minutes": int(environment.RESET_TTL.total_seconds() // 60),
    }


@router.delete("/accounts/{user_id}/sessions")
def revoke_sessions(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    """Log one account out everywhere without touching the account itself."""
    user = queries.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    return {"user_id": user.id, "revoked": queries.revoke_all_sessions(db, user.id)}


@router.post("/accounts/{user_id}/unlock")
def unlock_login(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    """Clear the login rate limiter for one account. Its key only, never the IP's."""
    user = queries.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    unlock("login", user.username)
    return {"user_id": user.id, "unlocked": True}


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
        for stage in readings.pipeline_snapshot(ws)
    ]


def _refused(refusal: members.Refusal) -> HTTPException:
    """Turn a refused membership gesture into the answer the panel reads by its code."""
    return HTTPException(refusal.status, refusal.message, headers={"X-Error-Code": refusal.code})
