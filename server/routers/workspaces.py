"""Which instances this account can work in, and which one it is looking at.

A workspace is a whole instance — its corpus, its graph, its exemplars profile, its bank,
its caches and its generations — so «tener varios perfiles de ejemplares o varios grafos»
is exactly «tener varios workspaces». That is why creating one is offered to any account
rather than reserved to the administrator: a teacher with two subjects needs two, and
nothing about the second one touches anybody else's data.

The active workspace is a preference stored on the account, not a permission. Every route
that reads instance data resolves membership on its own (`require_member`), so pointing
this at a workspace you are not a member of costs a 403 and never a read.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from variatio.core import languages
from variatio.instance import locale

from .. import auth, deps, runtime, settings
from ..db import generations, identity, repository
from ..db.models import OWNER, VIEWER, User, Workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class CreateBody(BaseModel):
    slug: str = Field(min_length=3, max_length=64)
    name: str = ""
    # The language its PROMPTS will be written in, and the only moment it can be decided:
    # the relation labels a build writes into `knowledge_graph.json` are what the loader
    # indexes by, so once anything is built the choice is baked into the artifacts.
    prompt_language: str = languages.DEFAULT


class RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _view(workspace: Workspace, role: str | None, active: bool, as_admin: bool = False) -> dict:
    return {
        "slug": workspace.slug,
        "name": workspace.name,
        "role": role,
        "active": active,
        "prompt_language": workspace.prompt_language,
        # An administrator sees every workspace in the switcher, including the ones they
        # are not a member of. Saying so is what keeps them from mistaking somebody else's
        # instance for their own.
        "as_admin": as_admin,
    }


@router.get("")
def listing(
    user: User = Depends(auth.current_user), db: DbSession = Depends(auth.db)
) -> dict:
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
    slug = body.slug.strip().lower()
    error = settings.slug_error(slug)
    if error:
        raise HTTPException(422, error)
    if repository.get_workspace(db, slug) is not None:
        raise HTTPException(409, f"Ya existe un workspace con el identificador '{slug}'.")

    error = languages.error(body.prompt_language)
    if error:
        raise HTTPException(422, error)

    workspace = repository.create_workspace(
        db, slug, body.name.strip() or slug, prompt_language=body.prompt_language
    )
    identity.grant(db, workspace.id, user.id, OWNER)
    user.active_workspace_id = workspace.id

    # The directory tree before the row is usable: every screen of a brand-new workspace
    # reads files, and an empty chain with no place to upload into is a dead end.
    ws = settings.workspace_for(slug)
    settings.provision(ws)
    # The file is what a build reads — the pipeline never touches the database — so the row
    # written above is the mirror and this is the truth.
    locale.set_prompt_language(ws, workspace.prompt_language)
    return {"workspace": _view(workspace, OWNER, active=True)}


@router.post("/{slug}/activate", dependencies=[Depends(auth.require_open)])
def activate(
    slug: str,
    user: User = Depends(auth.current_user),
    db: DbSession = Depends(auth.db),
) -> dict:
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")

    membership = identity.membership(db, workspace.id, user.id)
    if membership is None and not user.is_admin:
        raise HTTPException(403, f"No tienes acceso al workspace '{slug}'.")

    user.active_workspace_id = workspace.id
    return {
        "workspace": _view(
            workspace,
            membership.role if membership else OWNER,
            active=True,
            as_admin=membership is None,
        )
    }


@router.patch("/{slug}", dependencies=[auth.MANAGE])
def rename(slug: str, body: RenameBody, access: auth.Access = auth.MANAGE) -> dict:
    if slug != access.workspace.slug:
        raise HTTPException(
            409,
            "Solo se puede renombrar el workspace activo; cambia a él antes.",
        )
    access.workspace.name = body.name.strip()
    return {"workspace": _view(access.workspace, access.role, active=True)}


# Deleting is a real deletion, not a flag: the row cascades to artifacts, approvals, raw
# documents, memberships, generations and evaluation sessions. The directory tree is left
# alone on purpose — it holds the user's own uploaded documents, and a web request that
# quietly removes hundreds of megabytes of somebody's lecture notes is not a request
# anyone expects to be irreversible.
@router.delete("/{slug}", dependencies=[auth.MANAGE])
def remove(
    slug: str,
    access: auth.Access = auth.MANAGE,
    db: DbSession = Depends(auth.db),
) -> dict:
    if slug != access.workspace.slug:
        raise HTTPException(409, "Solo se puede borrar el workspace activo.")
    if len(repository.list_workspaces(db)) == 1:
        raise HTTPException(409, "No se puede borrar el único workspace de la instalación.")

    ws = access.ws
    db.delete(access.workspace)
    db.flush()
    deps.invalidate(ws.slug, "workspace eliminado")
    return {"deleted": slug, "path": str(ws.root)}


# LEAVING one, which is a different act from deleting it and only sometimes has the same
# consequence. `remove` above is the OWNER disposing of a shared instance; this is a person
# disposing of their own access, and any member may do it whatever their role — it acts on
# their own membership row and on nothing else.
#
# The two collapse into one when the person leaving is the last one linked to it: with the
# seat empty there is nobody left for the workspace to belong to, so the row goes with them.
# That holds even when the leaver is not the owner — the case exists (an owner's account was
# deleted, and `memberships` went with it), and refusing there would strand an instance that
# nobody but an administrator could ever open again.
#
# The DIRECTORY TREE IS LEFT ALONE, exactly as in `remove` and for the same reason: it holds
# the user's own uploaded documents, and a web request that quietly removes hundreds of
# megabytes of somebody's lecture notes is not a request anyone expects to be irreversible.
# An administrator can still re-import the tree.
#
# There is deliberately no «last workspace of the installation» guard here. `remove` has one
# and it predates the decision that an installation may hold ZERO workspaces and an account
# may belong to none — both are normal states the app renders on purpose, and refusing to
# let the last person out of the last instance would make «no workspace» reachable only by
# an administrator.
@router.delete("/{slug}/membership")
def leave(
    slug: str,
    user: User = Depends(auth.current_user),
    db: DbSession = Depends(auth.db),
) -> dict:
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")

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

    db.delete(workspace)
    db.flush()
    if user.active_workspace_id == workspace.id:
        user.active_workspace_id = None
    deps.invalidate(slug, "workspace eliminado al salir su último miembro")
    logger.info(f"[workspace] «{user.username}» era el último de «{slug}»; se eliminó")
    return {"left": slug, "deleted": True, "members_left": 0, "path": str(ws.root)}


# The chain of a workspace other than the active one, so the switcher can show what state
# each instance is in without making the browser change workspace to find out.
@router.get("/{slug}/summary")
def summary(
    slug: str,
    user: User = Depends(auth.current_user),
    db: DbSession = Depends(auth.db),
) -> dict:
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
