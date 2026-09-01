"""The installation's own panel: the accounts, the workspaces and how the study is going.

Every route here is behind `require_admin`, and the whole router exists under `/api/admin`
because `/api/workspaces`'s `auth.MANAGE` only ever reaches the ACTIVE workspace — tidying
up the installation from there would mean entering each instance in order to touch it.

INVITATIONS AND MEMBERSHIP ARE THE INSTALLATION ADMINISTRATOR'S ALONE. There is no
owner-scoped door: an owner owns their workspace's content and does not decide who else
exists. Two screens for one question is how an installation ends up with two answers.

What this is NOT: a second way into the pipeline. Nothing here builds, edits or approves
anything. It reads what the installation has recorded, hands out access, and exports a CSV.
The one thing it reads across accounts is the study — whose unit of analysis is a session,
and whose interesting question cannot be answered from inside one account. That bypass
lives in `auth.deps.access_for`, in one `if`, and nowhere else.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from study.api import store as evaluation_store

from .. import auth, deps, maintenance, review, runtime, settings, storage
from ..auth import deps as auth_deps
from ..auth.rate_limit import locked_seconds, throttle, unlock
from ..db import generations, identity, repository
from ..db.models import EDITOR, ROLES, Invite, User
from ..jobs import lanes as jobs_lanes

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class InviteBody(BaseModel):
    """What an invitation grants: a workspace and a role, or nothing at all.

    `workspace` may be absent — an invitation granting no membership creates an account
    and no access, which is the honest way to add somebody who will be given a workspace
    later. There is no evaluator profile here on purpose: the link binds the access and
    nothing else, and whoever registers answers for themselves.
    """

    workspace: str | None = None
    role: str = EDITOR


class MembershipBody(BaseModel):
    """The instance somebody is being let into, and with what role."""

    workspace: str
    role: str = EDITOR


class AdminBody(BaseModel):
    """Whether this account runs the installation."""

    is_admin: bool


class ProfileBody(BaseModel):
    """The evaluator profile being corrected: `teacher`, `student` or nothing."""

    evaluator_profile: str | None = None


class MaintenanceBody(BaseModel):
    """Whether the door is shut, and the notice shown while it is."""

    active: bool
    message: str | None = None


# WHO AND WHAT ----------------------------------------------------------------------------


def _lane_jobs() -> dict:
    """Report what is holding each lane, as a list and with the room it is filling.

    A list per lane and not one job: the remote lane holds as many as
    `CEREBRAS_MAX_CONCURRENT_JOBS` allows, so the oldest of them does not answer «what is
    this half of the engine doing», and N jobs means nothing without the capacity.
    """
    return {
        backend: {
            "capacity": jobs_lanes.capacity(backend),
            "jobs": [job.to_dict() for job in runtime.runner.holders_in(backend)],
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
            {"slug": w.slug, "role": m.role}
            for m, w in identity.memberships_for(db, user.id)
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
        "generations": generations.count_generations(db, workspace.id),
        "warm": workspace.slug in deps.warm_slugs(),
        "stages": _chain(workspace.slug),
        "disk": settings.disk_usage(settings.workspace_for(workspace.slug)),
    }


@router.get("/overview")
def overview(db: DbSession = Depends(auth.db)) -> dict:
    """Answer the whole panel: totals, every account, every instance and the queue."""
    workspaces = repository.list_workspaces(db)
    users = identity.list_users(db)
    generated = generations.generations_per_user(db)
    headers = evaluation_store.headers(db)
    by_account = {group["key"]: group for group in evaluation_store.by_account(headers)}

    running = runtime.runner.running()
    return {
        "totals": {
            "users": len(users),
            "workspaces": len(workspaces),
            "generations": generations.count_generations(db),
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
            "queued": len(runtime.runner.pending()),
            "warm_contexts": deps.warm_slugs(),
        },
    }


# ACCESS ----------------------------------------------------------------------------------
#
# The only way an account comes into existence, and the only way one enters a workspace.


@router.get("/invites")
def invites(db: DbSession = Depends(auth.db)) -> dict:
    """List the invitations still live."""
    return {"invites": [_invite(db, row) for row in identity.pending_invites(db)]}


@router.post("/invites", status_code=201)
def create_invite(
    body: InviteBody,
    request: Request,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Mint one single-use invitation and answer the link that IS the invitation.

    It is handed over by hand: expiring, bound to no address, and whoever redeems it
    chooses their own username — which is why it must not be left where its holder was
    not meant to be. An administrator session is not a licence to mint credentials
    without limit, hence the throttle.
    """
    throttle("invite", request, admin.username)
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'. Usa uno de {', '.join(ROLES)}.")

    workspace = None
    if body.workspace:
        workspace = repository.get_workspace(db, body.workspace)
        if workspace is None:
            raise HTTPException(404, f"No existe el espacio de trabajo '{body.workspace}'.")

    token = auth.new_token()
    invite = identity.create_invite(
        db,
        token_hash=auth.digest(token),
        ttl=settings.INVITE_TTL,
        workspace_id=workspace.id if workspace else None,
        role=body.role,
        created_by=admin.id,
    )

    return {
        "invite": _invite(db, invite),
        "link": f"{auth.base_url(request)}/invite?token={token}",
    }


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: int, db: DbSession = Depends(auth.db)) -> dict:
    """Withdraw an invitation before anybody redeems it."""
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe.")
    return {"revoked": identity.revoke_invite(db, invite_id)}


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
        raise HTTPException(404, f"No existe el espacio de trabajo '{body.workspace}'.")

    identity.grant(db, workspace.id, user.id, body.role)
    return {"user_id": user.id, "workspace": workspace.slug, "role": body.role}


@router.post("/accounts/{user_id}/profile")
def set_profile(user_id: int, body: ProfileBody, db: DbSession = Depends(auth.db)) -> dict:
    """Correct an account's evaluator profile, administrators included.

    It changes the wording of one question and how the study groups its results; it
    grants and withholds nothing, which is why withholding this control from anybody
    would be a restriction with no reason.
    """
    error = identity.profile_error(body.evaluator_profile)
    if error:
        raise HTTPException(422, error)
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")

    identity.set_evaluator_profile(db, user, body.evaluator_profile)
    return {"user_id": user.id, "evaluator_profile": user.evaluator_profile}


@router.delete("/accounts/{user_id}/memberships/{slug}")
def revoke_membership(user_id: int, slug: str, db: DbSession = Depends(auth.db)) -> dict:
    """Take one account's access to one instance away."""
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el espacio de trabajo '{slug}'.")
    identity.revoke_membership(db, workspace.id, user_id)
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
        raise HTTPException(404, f"No existe el espacio de trabajo '{slug}'.")
    workspace.name = body.name.strip()
    db.flush()
    logger.info(f"[admin] Espacio de trabajo '{slug}' renombrado a «{workspace.name}»")
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

    There is deliberately NO «last workspace of the installation» guard: an installation
    holding zero workspaces is a normal state the app renders on purpose, and `leave`
    already deletes the last one when its last member walks out.
    """
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el espacio de trabajo '{slug}'.")
    ws = settings.workspace_for(slug)
    # Tree before row: this way a failure leaves the row standing and the call retryable,
    # where the other order strands files nobody is on record as owning.
    try:
        removed = settings.destroy(ws)
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
    runtime.bus.publish(slug, None, "workspace.deleted", {"slug": slug})
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


@router.delete("/workspaces/{slug}/artifacts/{artifact}")
def delete_artifact(slug: str, artifact: str, db: DbSession = Depends(auth.db)) -> dict:
    """Empty one stage, leaving the workspace standing and the artifact «missing».

    What goes is the curated file, the draft and the cache derivations that spoke of it,
    which is what allows rebuilding. `.history/` is untouched, so a mistaken deletion is
    undone from «Restaurar» on the artifact's own screen — and that is what makes this
    button safe to offer at all.
    """
    if artifact not in review.ARTIFACTS:
        raise HTTPException(404, f"Artefacto desconocido: '{artifact}'.")
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el espacio de trabajo '{slug}'.")
    if artifact in runtime.runner.building_artifacts(slug):
        raise HTTPException(
            409, "Ese artefacto se está construyendo ahora mismo; cancela el trabajo antes."
        )

    ws = settings.workspace_for(slug)
    result = review.discard(ws, artifact)
    deps.invalidate(slug, f"'{artifact}' eliminado desde administración")
    runtime.bus.publish(slug, None, "pipeline.changed", {"artifact": artifact, "action": "discard"})
    return {"workspace": slug, **result}


@router.delete("/workspaces/{slug}/cache")
def clear_cache(slug: str, db: DbSession = Depends(auth.db)) -> dict:
    """Drop the regenerable half of a cache: the vectors and the converted markdown.

    The descriptions and the concept sources stay — they cost a model run. Refused while
    the workspace has work running or waiting, because that work reads these files.
    """
    if repository.get_workspace(db, slug) is None:
        raise HTTPException(404, f"No existe el espacio de trabajo '{slug}'.")
    # Every run of this workspace, on either lane: `current()` alone would miss the one on
    # the second lane whenever somebody else's older job holds the first.
    if runtime.runner.running(slug) or runtime.runner.pending(slug):
        raise HTTPException(409, "Ese espacio de trabajo tiene trabajo en curso o en cola; espera o cancélalo.")
    ws = settings.workspace_for(slug)
    result = settings.clear_cache(ws)
    deps.invalidate(slug, "caché vaciada desde administración")
    return {"workspace": slug, **result}


@router.get("/workspaces/{slug}/export")
def export_workspace(slug: str, db: DbSession = Depends(auth.db)) -> dict:
    """Answer the instance as the FILES say it is: what a checkout needs to run it.

    Read from disk and not from the database rows, because the files are the operational
    truth and the rows are their mirror.
    """
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el espacio de trabajo '{slug}'.")
    ws = settings.workspace_for(slug)
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
    running = runtime.runner.running()
    return {
        "running": running[0].to_dict() if running else None,
        "lanes": _lane_jobs(),
        "queued": [
            {**job.to_dict(), "queue_position": runtime.runner.queue_position(job.id)}
            for job in runtime.runner.pending()
        ],
    }


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str) -> dict:
    """Cancel any job of the installation, whatever workspace it belongs to."""
    if runtime.runner.get(job_id) is None:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'.")
    return {"cancelled": runtime.runner.cancel(job_id)}


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
    the account and leaves standing what it made — `generations.user_id` and
    `evaluation_sessions.user_id` are `SET NULL`, so deleting somebody must not delete the
    material a course was built on. Deleting yourself is refused, which is also what keeps
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
    Taking it from yourself is refused for the same reason deleting yourself is.
    """
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id and not body.is_admin:
        raise HTTPException(409, "No puedes quitarte la administración a ti mismo.")
    user.is_admin = body.is_admin
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
    identity.create_reset(db, user.id, auth.digest(token), settings.RESET_TTL)
    return {
        "user_id": user.id,
        "link": f"{auth.base_url(request)}/reset?token={token}",
        "expires_in_minutes": int(settings.RESET_TTL.total_seconds() // 60),
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


# HELPERS ---------------------------------------------------------------------------------


def _chain(slug: str) -> list[dict]:
    """Read one workspace's three stages from its files, without mounting its index."""
    ws = settings.workspace_for(slug)
    return [
        {
            "artifact": stage["artifact"],
            "label": stage["label"],
            "status": stage["status"],
            "is_autogenerated": stage["is_autogenerated"],
        }
        for stage in runtime.pipeline_snapshot(ws)
    ]


def _invite(db: DbSession, invite: Invite) -> dict:
    """Render one invitation for the panel. Never its token — that is handed over once."""
    workspace = invite.workspace
    author = identity.get_user_by_id(db, invite.created_by) if invite.created_by else None
    return {
        "id": invite.id,
        "role": invite.role,
        "workspace": workspace.name if workspace else None,
        "workspace_slug": workspace.slug if workspace else None,
        "created_at": invite.created_at.isoformat(),
        "expires_at": invite.expires_at.isoformat(),
        "created_by": author.username if author else None,
    }
