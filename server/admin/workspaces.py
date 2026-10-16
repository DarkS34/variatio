"""The installation's subjects, from the panel: renaming, deleting, ending a course, emptying.

Behind `require_admin`, under `/api/admin` like every route of the panel. It exists because `/api/workspaces`'s `auth.MANAGE` only ever reaches the
ACTIVE workspace: tidying up the installation from there would mean entering each instance in
order to touch it. The exercises generated in a subject are read here read-only, which no
other route shows anybody but their author.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from .. import auth
from .. import generations as generations_store
from ..auth import deps as auth_deps
from ..auth import queries
from ..bank import profile_edit
from ..classroom import members
from ..core import contexts, installation, process
from ..db import repository
from ..db.models import User
from ..pipeline import approvals, storage
from ..workspaces import trees as workspaces_trees

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


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
        removed = workspaces_trees.destroy(ws)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, f"No se pudo borrar '{ws.root}': {exc}") from exc

    # Whoever was sitting in it is moved before the row goes: a dangling pointer leaves
    # them holding a slug the API answers 404 for, with the switcher offering no way back.
    rehomed = auth_deps.rehome_accounts(db, workspace)

    db.delete(workspace)
    db.flush()
    contexts.invalidate(slug, "workspace eliminado")
    # Heard only by whoever is looking at the instance that has just stopped existing,
    # which is exactly who has to reload.
    process.bus.publish(slug, None, "workspace.deleted", {"slug": slug})
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
    if artifact in process.runner.building_artifacts(slug):
        raise HTTPException(
            409, "Ese artefacto se está construyendo ahora mismo; cancela el trabajo antes."
        )

    ws = installation.workspace_for(slug)
    result = approvals.discard(ws, artifact)
    contexts.invalidate(slug, f"'{artifact}' eliminado desde administración")
    process.bus.publish(slug, None, "pipeline.changed", {"artifact": artifact, "action": "discard"})
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
    if process.runner.running(slug) or process.runner.pending(slug):
        raise HTTPException(409, "Esa asignatura tiene trabajo en curso o en cola; espera o cancélalo.")
    ws = installation.workspace_for(slug)
    result = workspaces_trees.clear_cache(ws)
    contexts.invalidate(slug, "caché vaciada desde administración")
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
    accounts = {user.id: user for user in queries.list_users(db)}
    pairs, total = generations_store.list_all(
        ws, author=author, query=q, limit=limit, offset=offset
    )
    return {
        "workspace": slug,
        "generations": [
            generations_store.row_view(record, accounts.get(user_id)) for user_id, record in pairs
        ],
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
        "bank_visibility": ws.bank_visibility_path,
    }
    return {
        "workspace": slug,
        "name": workspace.name,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "files": {key: storage.read_json(path) for key, path in files.items() if path.is_file()},
    }
