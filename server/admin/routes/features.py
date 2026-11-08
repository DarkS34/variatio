"""Who the functions are for: the modes and lists of generating, the evaluation, the tutor, the chat.

Behind `require_admin`, under `/api/admin` like every route of the panel.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ... import auth
from ...auth import features, queries
from ...db import repository
from ...db.models import User

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class FeatureBody(BaseModel):
    """Who one function is for: its mode and, when sent, its accounts and subjects."""

    mode: str
    accounts: list[int] | None = None
    workspaces: list[str] | None = None


class OwnSwitchBody(BaseModel):
    """Whether the administrator asking uses one function in their own account."""

    on: bool


@router.get("/features")
def read_features(
    admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
    """Answer who each function is for, and which the administrator asking uses (`mine`)."""
    return _payload(db, admin)


@router.put("/features/{feature}/mine")
def switch_mine(
    feature: str,
    body: OwnSwitchBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Switch one function on or off for the administrator asking, and for nobody else (D-245)."""
    if feature not in features.GATED:
        raise HTTPException(404, f"No existe la función '{feature}'.")
    features.switch_own(db, admin, feature, body.on)
    logger.info(
        "[funciones] {} se ha {} '{}' para su cuenta",
        admin.username,
        "abierto" if body.on else "cerrado",
        feature,
    )
    return _payload(db, admin)


def _payload(db: DbSession, admin: User) -> dict:
    """Render every function's mode and lists, and what the administrator asking uses."""
    return {
        "features": features.snapshot(db),
        "mine": {feature: not features.switched_off(admin, feature) for feature in features.GATED},
    }


@router.put("/features/{feature}")
def set_feature(
    feature: str,
    body: FeatureBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Set who one function is for.

    A list is replaced only when it is sent — `accounts`, or `workspaces` for a function a
    subject may be listed for — so switching the mode alone keeps both.
    """
    if feature not in features.GATED:
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
    return _payload(db, admin)
