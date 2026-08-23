"""The study's own tab of the installation panel.

Same prefix and same `require_admin` as `server/routers/admin.py`, and mounted beside it
by `study.api.install`: the routes are the administrator's, the arithmetic behind them is
the study's, and this is the seam between the two.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server import auth
from server.db import repository
from server.db.models import User

from .. import ARM_LABELS, ARMS
from . import queries
from . import store as evaluation_store

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class DeleteBody(BaseModel):
    ids: list[str]


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
    row = queries.get_evaluation(db, session_id)
    if row is None:
        raise HTTPException(404, f"No existe la sesión '{session_id}'.")
    return {
        "session": row.trace,
        "workspace": row.workspace.slug if row.workspace else None,
        "account": row.user.username if row.user else None,
    }


@router.delete("/evaluations")
def delete_sessions(
    body: DeleteBody,
    db: DbSession = Depends(auth.db),
    admin: User = Depends(auth.require_admin),
) -> dict:
    ids = list(dict.fromkeys(i for i in body.ids if i))
    if not ids:
        raise HTTPException(422, "No se ha indicado ninguna sesión.")
    deleted = queries.delete_evaluations(db, ids)
    logger.warning(
        f"[estudio] «{admin.username}» borró {len(deleted)} sesión(es) de evaluación"
    )
    return {"deleted": deleted, "missing": [i for i in ids if i not in deleted]}


def _headers(db: DbSession, workspace: str | None = None) -> list[dict]:
    workspace_id = None
    if workspace:
        row = repository.get_workspace(db, workspace)
        if row is None:
            raise HTTPException(404, f"No existe el workspace '{workspace}'.")
        workspace_id = row.id
    return evaluation_store.headers(db, workspace_id)


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
