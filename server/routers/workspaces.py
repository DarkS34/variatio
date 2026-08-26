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
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from .. import auth, deps, runtime, settings
from ..db import generations, identity, repository
from ..db.models import OWNER, VIEWER, User, Workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class CreateBody(BaseModel):
    slug: str = Field(min_length=3, max_length=64)
    name: str = ""


class RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _view(workspace: Workspace, role: str | None, active: bool, as_admin: bool = False) -> dict:
    return {
        "slug": workspace.slug,
        "name": workspace.name,
        "role": role,
        "active": active,
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

    workspace = repository.create_workspace(db, slug, body.name.strip() or slug)
    identity.grant(db, workspace.id, user.id, OWNER)
    user.active_workspace_id = workspace.id

    # The directory tree before the row is usable: every screen of a brand-new workspace
    # reads files, and an empty chain with no place to upload into is a dead end.
    settings.provision(settings.workspace_for(slug))
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
