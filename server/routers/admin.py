"""The installation's own panel: how the study is going, across accounts and workspaces.

This router is the documented exception to phase 2's «an administrator runs the
installation, they do not read other people's instances». Taken by explicit user request
in phase 3, because the evaluation is a study whose unit of analysis is a session and
whose interesting question — «¿va ganando el sistema, y con qué evaluadores?» — cannot be
answered from inside one account. The bypass lives in `auth.deps.access_for`, one `if`,
and every route here is behind `require_admin`.

What it is NOT: a second way into the pipeline. Nothing here builds, edits or approves
anything. It reads what the installation has recorded and hands back a CSV.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session as DbSession

from variant_generator.evaluation import ARM_LABELS, ARMS

from .. import auth, deps, evaluation_store, runtime
from ..db import identity, repository, study
from ..db.models import User

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


# WHO AND WHAT ----------------------------------------------------------------------------


@router.get("/overview")
def overview(db: DbSession = Depends(auth.db)) -> dict:
    workspaces = repository.list_workspaces(db)
    users = identity.list_users(db)
    generated = study.generations_per_user(db)
    headers = _headers(db)
    by_account = {group["key"]: group for group in evaluation_store.by_account(headers)}

    running = runtime.runner.current()
    return {
        "totals": {
            "users": len(users),
            "workspaces": len(workspaces),
            "generations": study.count_generations(db),
            "evaluations": len(headers),
            "decided": sum(1 for h in headers if h.get("chosen_at")),
        },
        "accounts": [
            {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "is_admin": user.is_admin,
                "disabled": not user.active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "workspaces": [
                    {"slug": w.slug, "role": m.role}
                    for m, w in identity.memberships_for(db, user.id)
                ],
                "generations": generated.get(user.id, 0),
                "evaluations": by_account.get(user.id, {}).get("sessions", 0),
                "decided": by_account.get(user.id, {}).get("decided", 0),
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
                "generations": study.count_generations(db, workspace.id),
                "warm": workspace.slug in deps.warm_slugs(),
            }
            for workspace in workspaces
        ],
        "engine": {
            "busy": running is not None,
            "job": running.to_dict() if running else None,
            "queued": len(runtime.runner.pending()),
            "warm_contexts": deps.warm_slugs(),
        },
    }


# THE STUDY -------------------------------------------------------------------------------


@router.get("/evaluations")
def evaluations(
    workspace: str | None = None,
    account: int | None = None,
    db: DbSession = Depends(auth.db),
) -> dict:
    headers = _headers(db, workspace=workspace)
    if account is not None:
        headers = [h for h in headers if h.get("account_id") == account]

    return {
        "aggregates": evaluation_store.aggregates(headers),
        "by_account": evaluation_store.by_account(headers),
        "by_workspace": evaluation_store.by_workspace(headers),
        "per_day": evaluation_store.per_day(headers),
        "arms": [{"key": arm, "label": ARM_LABELS[arm]} for arm in ARMS],
        "filters": {
            "workspace": workspace,
            "account": account,
            "workspaces": sorted({h["workspace"] for h in _headers(db) if h["workspace"]}),
        },
        # Newest first, and every one openable: the point of the panel is being able to
        # go from «este evaluador nunca elige el sistema» to the sessions that say so.
        "sessions": [_row(h) for h in sorted(
            headers, key=lambda h: h.get("created_at") or 0, reverse=True
        )],
    }


@router.get("/evaluations/export.csv")
def export(
    workspace: str | None = None,
    account: int | None = None,
    db: DbSession = Depends(auth.db),
) -> Response:
    headers = _headers(db, workspace=workspace)
    if account is not None:
        headers = [h for h in headers if h.get("account_id") == account]
    return Response(
        content=evaluation_store.export_csv(headers),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="evaluaciones.csv"'},
    )


# The full trace of one session, reveal included. An administrator reading this is reading
# research data they are entitled to; the evaluator's own blinding is unaffected, because
# nothing here writes and the session is already judged or already theirs to judge.
@router.get("/evaluations/{session_id}")
def session_detail(session_id: str, db: DbSession = Depends(auth.db)) -> dict:
    row = study.get_evaluation(db, session_id)
    if row is None:
        raise HTTPException(404, f"No existe la sesión '{session_id}'.")
    return {
        "session": row.trace,
        "workspace": row.workspace.slug if row.workspace else None,
        "account": row.user.username if row.user else None,
    }


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


# HELPERS ---------------------------------------------------------------------------------


def _headers(db: DbSession, workspace: str | None = None) -> list[dict]:
    workspace_id = None
    if workspace:
        row = repository.get_workspace(db, workspace)
        if row is None:
            raise HTTPException(404, f"No existe el workspace '{workspace}'.")
        workspace_id = row.id
    return [
        evaluation_store.header(row, user, row.workspace.slug if row.workspace else None)
        for row, user in study.all_evaluations(db, workspace_id)
    ]


def _row(header: dict) -> dict:
    return {
        "id": header["id"],
        "created_at": header.get("created_at"),
        "workspace": header.get("workspace"),
        "account": header.get("account"),
        "account_id": header.get("account_id"),
        "concepts": header.get("concepts") or [],
        "item_type": header.get("item_type"),
        "choice": header.get("choice"),
        "choice_arm": header.get("choice_arm"),
        "chosen_at": header.get("chosen_at"),
        "think": bool(header.get("think", True)),
        "rating": header.get("rating"),
        "arm_status": header.get("arm_status") or {},
        "arm_elapsed_ms": header.get("arm_elapsed_ms") or {},
        "evaluator_note": header.get("evaluator_note"),
    }
