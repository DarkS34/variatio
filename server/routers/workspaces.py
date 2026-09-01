"""Which instances this account can work in, and which one it is looking at.

A workspace is a whole instance — its corpus, its graph, its exemplars profile, its bank,
its caches and its generations — so «tener varios perfiles de ejemplares o varios grafos»
is exactly «tener varios workspaces». That is why creating one is offered to any account
rather than reserved to the administrator: a teacher with two subjects needs two, and
nothing about the second touches anybody else's data.

Authorisation is declared per route here rather than on the router, because the routes do
not share one level: listing, creating and activating resolve the account themselves,
`remove` demands `auth.MANAGE`, and `leave` acts on the caller's own membership row.

DELETING TAKES THE DIRECTORY TREE WITH IT EXACTLY WHEN NOBODY ELSE IS A MEMBER, and both
doors — `remove` and `leave` — obey that one condition and report it as `files_removed`.
With other members still in it their lecture notes are in there and they are losing the
instance without having asked; with nobody left there is no such person, and the files
would pile up under a slug the installation records nowhere. Two orderings are part of
the rule: the roster is read BEFORE the cascade takes the rows away, and the tree goes
BEFORE the row, so a failure leaves a retryable row rather than an orphan tree.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from variatio.core import languages
from variatio.instance import locale

from .. import auth, deps, runtime, settings
from ..auth import deps as auth_deps
from ..db import generations, identity, repository
from ..db.models import OWNER, VIEWER, User, Workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class CreateBody(BaseModel):
    """A new instance: its slug, its display name and the language of its prompts."""

    slug: str = Field(min_length=3, max_length=64)
    name: str = ""
    # The only moment the prompt language can be decided: the relation labels a build
    # writes into `knowledge_graph.json` are what the loader indexes by, so once anything
    # is built the choice is baked into the artifacts.
    prompt_language: str = languages.DEFAULT


def _view(workspace: Workspace, role: str | None, active: bool, as_admin: bool = False) -> dict:
    """Render one workspace for the switcher, saying when the role is the admin bypass.

    An administrator sees every instance in the switcher, the ones they are not a member
    of included; `as_admin` is what keeps them from mistaking one for their own.
    """
    return {
        "slug": workspace.slug,
        "name": workspace.name,
        "role": role,
        "active": active,
        "prompt_language": workspace.prompt_language,
        "as_admin": as_admin,
    }


@router.get("")
def listing(
    user: User = Depends(auth.current_user), db: DbSession = Depends(auth.db)
) -> dict:
    """Answer the instances this account can open, and which one it lands in."""
    rows = identity.memberships_for(db, user.id)
    mine = {workspace.id: membership.role for membership, workspace in rows}
    current = auth.current_workspace_for(db, user)
    active_id = current.id if current else None

    workspaces = [workspace for _, workspace in rows]
    if user.is_admin:
        known = {w.id for w in workspaces}
        workspaces += [w for w in repository.list_workspaces(db) if w.id not in known]

    return {
        "workspaces": [
            _view(
                workspace,
                mine.get(workspace.id) or (OWNER if user.is_admin else None),
                workspace.id == active_id,
                as_admin=workspace.id not in mine,
            )
            for workspace in workspaces
        ],
        "active": current.slug if current else None,
        "can_create": True,
    }


@router.post("", status_code=201, dependencies=[Depends(auth.require_open)])
def create(
    body: CreateBody,
    user: User = Depends(auth.current_user),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Create an instance, make the caller its owner, and activate it."""
    slug = body.slug.strip().lower()
    error = settings.slug_error(slug)
    if error:
        raise HTTPException(422, error)
    if repository.get_workspace(db, slug) is not None:
        raise HTTPException(409, f"Ya existe una asignatura con el identificador '{slug}'.")

    error = languages.error(body.prompt_language)
    if error:
        raise HTTPException(422, error)

    workspace = repository.create_workspace(
        db, slug, body.name.strip() or slug, prompt_language=body.prompt_language
    )
    identity.grant(db, workspace.id, user.id, OWNER)
    user.active_workspace_id = workspace.id

    # The directory tree before the row is usable: every screen of a brand-new workspace
    # reads files, and an empty chain with nowhere to upload into is a dead end.
    ws = settings.workspace_for(slug)
    settings.provision(ws)
    # The file is what a build reads — the pipeline never touches the database — so the
    # row written above is the mirror and this is the truth.
    locale.set_prompt_language(ws, workspace.prompt_language)
    return {"workspace": _view(workspace, OWNER, active=True)}


@router.post("/{slug}/activate", dependencies=[Depends(auth.require_open)])
def activate(
    slug: str,
    user: User = Depends(auth.current_user),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Point the account at another instance it is allowed to open."""
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")

    membership = identity.membership(db, workspace.id, user.id)
    if membership is None and not user.is_admin:
        raise HTTPException(403, f"No tienes acceso a la asignatura '{slug}'.")

    user.active_workspace_id = workspace.id
    return {
        "workspace": _view(
            workspace,
            membership.role if membership else OWNER,
            active=True,
            as_admin=membership is None,
        )
    }


# THE NAME IS NOT EDITABLE FROM HERE, and there is no route for it in this router. A
# workspace is named when it is created and renamed only by an administrator, through
# `PATCH /api/admin/workspaces/{slug}`: what a name is worth is that everybody reading a
# screen means the same instance by it, and the panel is the one place somebody sees every
# instance at once and can tell whether a new name collides.


@router.delete("/{slug}", dependencies=[auth.MANAGE])
def remove(
    slug: str,
    access: auth.Access = auth.MANAGE,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Delete the active instance, taking its files when nobody else is a member.

    A real deletion, not a flag: the row cascades to artifacts, approvals, raw documents,
    memberships, generations and evaluation sessions. `files_removed` is what the caller
    needs afterwards, because the confirmation dialog promised one of two things.
    """
    if slug != access.workspace.slug:
        raise HTTPException(409, "Solo se puede borrar la asignatura activa.")

    ws = access.ws
    # Read before the cascade takes the rows away. An administrator reaching this through
    # the bypass holds no membership of their own, so the question is «is anybody else in
    # it» and not «does it have members».
    others = [
        m
        for m, _ in identity.members_of(db, access.workspace.id)
        if m.user_id != access.user.id
    ]
    removed = False
    if not others:
        # Tree before row: this way a failure leaves the row standing and the call
        # retryable, where the other order strands files nobody is on record as owning.
        try:
            removed = settings.destroy(ws)
        except (ValueError, OSError) as exc:
            raise HTTPException(409, f"No se pudo borrar '{ws.root}': {exc}") from exc

    # Whoever was sitting in it is moved before the row goes. The FK is `SET NULL`, so
    # without this the database strands every one of them at «no workspace» — including
    # the people who have another one to fall back to.
    rehomed = auth_deps.rehome_accounts(db, access.workspace)
    db.delete(access.workspace)
    db.flush()
    deps.invalidate(ws.slug, "workspace eliminado")
    # Heard only by whoever is looking at the instance that has just stopped existing,
    # which is exactly who has to reload.
    runtime.bus.publish(slug, None, "workspace.deleted", {"slug": slug})
    return {
        "deleted": slug,
        "path": str(ws.root),
        "rehomed": rehomed,
        # The one entry of `rehomed` the calling tab needs, so it can move straight to the
        # surviving instance instead of blanking to «ningún workspace» until `me` answers.
        "landed": rehomed.get(access.user.username),
        "files_removed": removed,
    }


@router.delete("/{slug}/membership")
def leave(
    slug: str,
    user: User = Depends(auth.current_user),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Give up your own access to an instance, deleting it if you were the last one in it.

    A different act from `remove` above — that is the owner disposing of a shared
    instance, this is a person disposing of their own access, and any member may do it
    whatever their role. The two collapse into one when the person leaving is the last
    one linked to it: with the seat empty there is nobody left for the workspace to belong
    to, so the row and the tree go with them. That holds even when the leaver is not the
    owner — the case exists (an owner's account was deleted and `memberships` went with
    it), and refusing there would strand an instance only an administrator could reopen.

    There is deliberately no «last workspace of the installation» guard: an installation
    holding zero workspaces and an account belonging to none are both normal states the
    app renders on purpose.
    """
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe la asignatura '{slug}'.")

    # An administrator reaches every instance through the bypass and usually holds no row
    # at all. There is nothing for them to leave, and deleting somebody else's workspace
    # from this route would be a different act wearing this one's name.
    membership = identity.membership(db, workspace.id, user.id)
    if membership is None:
        raise HTTPException(
            409,
            f"No formas parte de '{slug}': no hay acceso tuyo que quitar. "
            "Un administrador lo borra desde «Administración».",
        )

    others = [m for m, _ in identity.members_of(db, workspace.id) if m.user_id != user.id]
    ws = settings.workspace_for(slug)

    if others:
        db.delete(membership)
        db.flush()
        if user.active_workspace_id == workspace.id:
            user.active_workspace_id = None
        logger.info(f"[workspace] «{user.username}» salió de «{slug}»")
        return {"left": slug, "deleted": False, "members_left": len(others)}

    # Tree before row, as in `remove`: a failure leaves the row and the membership
    # standing and the call retryable.
    try:
        removed = settings.destroy(ws)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, f"No se pudo borrar '{ws.root}': {exc}") from exc

    db.delete(workspace)
    db.flush()
    if user.active_workspace_id == workspace.id:
        user.active_workspace_id = None
    deps.invalidate(slug, "asignatura eliminada al salir su último miembro")
    logger.info(f"[workspace] «{user.username}» era el último de «{slug}»; se eliminó")
    return {
        "left": slug,
        "deleted": True,
        "members_left": 0,
        "path": str(ws.root),
        "files_removed": removed,
    }


@router.get("/{slug}/summary")
def summary(
    slug: str,
    user: User = Depends(auth.current_user),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Answer another instance's chain, so the switcher can show its state in place."""
    workspace = auth.resolve_workspace(db, user, slug)
    access = auth.access_for(db, user, workspace, VIEWER)
    stages = runtime.pipeline_snapshot(access.ws)
    return {
        "slug": workspace.slug,
        "name": workspace.name,
        "role": access.role,
        "stages": [
            {"artifact": s["artifact"], "label": s["label"], "status": s["status"]}
            for s in stages
        ],
        "ready": all(s["status"] == "approved" for s in stages),
        "generations": generations.count_generations(db, workspace.id),
    }
