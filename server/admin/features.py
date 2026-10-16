"""Who the optional functions are for: the evaluation's and the tutor's modes and lists.

Behind `require_admin`, under `/api/admin` like every route of the panel.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import auth
from ..auth import features, queries
from ..db import repository
from ..db.models import User

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class FeatureBody(BaseModel):
    """Who one optional function is for: its mode and, when sent, its accounts and subjects."""

    mode: str
    accounts: list[int] | None = None
    workspaces: list[str] | None = None


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
        missing = [uid for uid in body.accounts if queries.get_user_by_id(db, uid) is None]
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
