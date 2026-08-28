"""The installation's own panel: the accounts, the workspaces and how the study is going.

This router is the documented exception to phase 2's «an administrator runs the
installation, they do not read other people's instances». Taken by explicit user request
in phase 3, because the evaluation is a study whose unit of analysis is a session and
whose interesting question — «¿va ganando el sistema, y con qué evaluadores?» — cannot be
answered from inside one account. The bypass lives in `auth.deps.access_for`, one `if`,
and every route here is behind `require_admin`.

What it is NOT: a second way into the pipeline. Nothing here builds, edits or approves
anything. It reads what the installation has recorded, hands out access, and exports a CSV.

Handing out access is new: issuing invitations and moving people between workspaces used
to be an owner's job, done from a dialog in the account menu, while this panel listed the
same accounts and could only enable or disable them. Two screens for one question is how
you end up with two answers, so they are one — this one — and only the installation's
administrator gets it, by explicit user request. An owner still owns their workspace's
content; they no longer decide who else exists.
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
    """`workspace` is a slug, or nothing: an invitation that grants no membership creates
    an account and no access, which is the honest way to add someone who will be given a
    workspace later. There is no evaluator profile here on purpose — the link binds nothing
    beyond the access, and the profile is answered by whoever registers."""

    workspace: str | None = None
    role: str = EDITOR


class MembershipBody(BaseModel):
    workspace: str
    role: str = EDITOR


class AdminBody(BaseModel):
    is_admin: bool


class ProfileBody(BaseModel):
    evaluator_profile: str | None = None


class MaintenanceBody(BaseModel):
    active: bool
    message: str | None = None


# WHO AND WHAT ----------------------------------------------------------------------------


def _lane_jobs() -> dict:
    return {
        backend: (job.to_dict() if job is not None else None)
        for backend, job in (
            (b, runtime.runner.current_in(b)) for b in jobs_lanes.BACKENDS
        )
    }


@router.get("/overview")
def overview(db: DbSession = Depends(auth.db)) -> dict:
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
            {
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
            for user in users
        ],
        "workspaces": [
            {
                "id": workspace.id,
                "slug": workspace.slug,
                "name": workspace.name,
                "created_at": workspace.created_at.isoformat()
                if workspace.created_at
                else None,
                "members": len(identity.members_of(db, workspace.id)),
                "generations": generations.count_generations(db, workspace.id),
                "warm": workspace.slug in deps.warm_slugs(),
                # Each instance's chain, so a stage can be emptied from here without switching to it. It
                # is reading three files per workspace, not mounting its index.
                "stages": _chain(workspace.slug),
                "disk": settings.disk_usage(settings.workspace_for(workspace.slug)),
            }
            for workspace in workspaces
        ],
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
    return {"invites": [_invite(db, row) for row in identity.pending_invites(db)]}


@router.post("/invites", status_code=201)
def create_invite(
    body: InviteBody,
    request: Request,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    # An administrator session is not a licence to mint credentials without limit, and the
    # bucket already existed for the owner-scoped route this replaces.
    throttle("invite", request, admin.username)
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'. Usa uno de {', '.join(ROLES)}.")

    workspace = None
    if body.workspace:
        workspace = repository.get_workspace(db, body.workspace)
        if workspace is None:
            raise HTTPException(404, f"No existe el workspace '{body.workspace}'.")

    token = auth.new_token()
    invite = identity.create_invite(
        db,
        token_hash=auth.digest(token),
        ttl=settings.INVITE_TTL,
        workspace_id=workspace.id if workspace else None,
        role=body.role,
        created_by=admin.id,
    )

    # The link IS the invitation: single-use, expiring, and handed over by whoever issued
    # it. There is no address bound to it, so the person redeeming it chooses their own
    # username — which is why it must not be left anywhere its holder was not meant to be.
    return {
        "invite": _invite(db, invite),
        "link": f"{auth.base_url(request)}/invite?token={token}",
    }


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: int, db: DbSession = Depends(auth.db)) -> dict:
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe.")
    return {"revoked": identity.revoke_invite(db, invite_id)}


@router.post("/accounts/{user_id}/memberships")
def grant_membership(
    user_id: int, body: MembershipBody, db: DbSession = Depends(auth.db)
) -> dict:
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'.")
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    workspace = repository.get_workspace(db, body.workspace)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{body.workspace}'.")

    identity.grant(db, workspace.id, user.id, body.role)
    return {"user_id": user.id, "workspace": workspace.slug, "role": body.role}


# Correcting a profile after the fact, for the accounts that predate it and for the ones
# invited with the wrong one. It changes the wording of one question and how the study
# groups the results; it grants and withholds nothing, which is why it is not `MembershipBody`.
@router.post("/accounts/{user_id}/profile")
def set_profile(user_id: int, body: ProfileBody, db: DbSession = Depends(auth.db)) -> dict:
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
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    identity.revoke_membership(db, workspace.id, user_id)
    return {"user_id": user_id, "workspace": slug}


# WORKSPACES ------------------------------------------------------------------------------
#
# What this panel writes about instances: their name, and their removal. It builds, edits
# and approves nothing. It lives here and not under `/api/workspaces` because that requires
# membership of the ACTIVE workspace — when what is needed is to tidy up the installation,
# that forces entering each instance in order to touch it, the exact opposite.


class RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)


# Renaming is the administrator's and nobody else's (2026-08-28, explicit user request):
# the owner's route is gone, so this is the only door. Only the NAME changes — the slug
# names the directory tree, the `X-Workspace` header and every row that points at the
# workspace, so renaming it would be a migration and not a rename.
@router.patch("/workspaces/{slug}")
def rename_workspace(slug: str, body: RenameBody, db: DbSession = Depends(auth.db)) -> dict:
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    workspace.name = body.name.strip()
    db.flush()
    logger.info(f"[admin] Workspace '{slug}' renombrado a «{workspace.name}»")
    return {"slug": slug, "name": workspace.name}


@router.delete("/workspaces/{slug}")
def delete_workspace(
    slug: str,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    # There is deliberately NO «last workspace of the installation» guard: an installation
    # holding zero workspaces is a normal state the app renders on purpose, and `leave`
    # already deletes the last one when its last member walks out — so the guard refused
    # the tidy way of doing what the untidy one allowed.
    ws = settings.workspace_for(slug)
    # The tree first: if the row goes and deleting the directory fails, files are left whose
    # owner is no longer on record. The other way round, a failure leaves the row and retries.
    try:
        removed = settings.destroy(ws)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, f"No se pudo borrar '{ws.root}': {exc}") from exc

    # Whoever was sitting in it is moved to wherever they land now, before the row goes:
    # leaving the pointer dangling left them holding a slug the API answers 404 for, on
    # every request, with the switcher offering no way back.
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
        # Where the caller ends up, which is the one entry of `rehomed` the tab that made
        # the request needs — and is `None` both when they were not in it and when they have
        # nowhere left to go, two states the panel draws the same way: it stays put.
        "landed": rehomed.get(admin.username),
    }


# Empty a stage. Leaves the workspace standing and its artifact «missing», which is what
# allows rebuilding it: what is deleted is the curated file, the draft and the cache
# derivations that spoke of it. `.history/` is untouched, so a mistaken deletion is undone
# from «Restaurar» on the artifact's screen.
@router.delete("/workspaces/{slug}/artifacts/{artifact}")
def delete_artifact(slug: str, artifact: str, db: DbSession = Depends(auth.db)) -> dict:
    if artifact not in review.ARTIFACTS:
        raise HTTPException(404, f"Artefacto desconocido: '{artifact}'.")
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    if artifact in runtime.runner.building_artifacts(slug):
        raise HTTPException(
            409, "Ese artefacto se está construyendo ahora mismo; cancela el trabajo antes."
        )

    ws = settings.workspace_for(slug)
    result = review.discard(ws, artifact)
    deps.invalidate(slug, f"'{artifact}' eliminado desde administración")
    runtime.bus.publish(slug, None, "pipeline.changed", {"artifact": artifact, "action": "discard"})
    return {"workspace": slug, **result}


# The regenerable half of the cache — vectors and converted markdown. Refused while the
# workspace has work running or waiting, because that work is what reads those files.
@router.delete("/workspaces/{slug}/cache")
def clear_cache(slug: str, db: DbSession = Depends(auth.db)) -> dict:
    if repository.get_workspace(db, slug) is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    # Every run of this workspace, on either lane: asking `current()` alone would miss the
    # one on the second lane whenever somebody else's older job holds the first.
    if runtime.runner.running(slug) or runtime.runner.pending(slug):
        raise HTTPException(409, "Ese workspace tiene trabajo en curso o en cola; espera o cancélalo.")
    ws = settings.workspace_for(slug)
    result = settings.clear_cache(ws)
    deps.invalidate(slug, "caché vaciada desde administración")
    return {"workspace": slug, **result}


# The instance as the files say it is — what a checkout would need to run it elsewhere.
# Read from disk and not from the database rows, because the files are the operational
# truth (2026-08-23) and the rows mirror them.
@router.get("/workspaces/{slug}/export")
def export_workspace(slug: str, db: DbSession = Depends(auth.db)) -> dict:
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
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


# `running` is the oldest of them, kept as it was; `lanes` is the honest picture now that
# the queue serialises per backend and two jobs can be in flight at once.
@router.get("/jobs")
def job_queue() -> dict:
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
    if runtime.runner.get(job_id) is None:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'.")
    return {"cancelled": runtime.runner.cancel(job_id)}


# ACCOUNTS --------------------------------------------------------------------------------


@router.post("/accounts/{user_id}/disable")
def disable(
    user_id: int, admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
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
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    user.disabled_at = None
    return {"enabled": user_id}


# The other half of `disable`, and deliberately not the same thing: disabling keeps the
# account and shuts the door, this removes the account and leaves standing what it made.
# Both exist because they answer different questions — «esta persona ya no entra» and «esta
# cuenta no debería haber existido» — and having only the first left the panel unable to
# clean up after a mistyped invitation.
#
# Deleting yourself is refused, which is also what keeps the installation from losing its
# last administrator: whoever is calling this is an active one, and stays.
@router.delete("/accounts/{user_id}")
def delete_account(
    user_id: int, admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id:
        raise HTTPException(409, "No puedes borrar tu propia cuenta.")

    username = user.username
    identity.delete_user(db, user)
    return {"deleted": user_id, "username": username}


# Administration is a flag on the account and the bypass it buys lives in one `if`
# (`auth.deps.access_for`). Taking it from yourself is refused for the same reason
# deleting yourself is: whoever calls this is an administrator, and stays one.
@router.post("/accounts/{user_id}/admin")
def set_admin(
    user_id: int,
    body: AdminBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id and not body.is_admin:
        raise HTTPException(409, "No puedes quitarte la administración a ti mismo.")
    user.is_admin = body.is_admin
    db.flush()
    return {"user_id": user.id, "is_admin": user.is_admin}


# The same link `/forgot` would mail, handed to the administrator instead: with no SMTP the
# only route to a locked-out person is by hand, and this is where the administrator is. It
# is issued, not sent, and it expires like any other.
@router.post("/accounts/{user_id}/reset-link")
def reset_link(user_id: int, request: Request, db: DbSession = Depends(auth.db)) -> dict:
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
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    return {"user_id": user.id, "revoked": identity.revoke_all_sessions(db, user.id)}


@router.post("/accounts/{user_id}/unlock")
def unlock_login(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    unlock("login", user.username)
    return {"user_id": user.id, "unlocked": True}


# THE DOOR --------------------------------------------------------------------------------


# Closing the installation is written here and nowhere else, like everything that decides
# who gets in. Reading it does NOT go through here: `GET /api/maintenance` asks for no
# session, because the notice has to reach whoever has not got in yet.
@router.get("/maintenance")
def read_maintenance() -> dict:
    return maintenance.state()


@router.post("/maintenance")
def set_maintenance(
    body: MaintenanceBody, admin: User = Depends(auth.require_admin)
) -> dict:
    return maintenance.set_state(body.active, body.message, admin.username)


# HELPERS ---------------------------------------------------------------------------------


def _chain(slug: str) -> list[dict]:
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
