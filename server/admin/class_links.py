"""Every subject's class links, as the panel lists them: pausing and revoking one.

Behind `require_admin`, under `/api/admin` like every route of the panel.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import auth
from ..auth import queries
from ..db.models import ClassGroup, ClassLink, User

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class ClassLinkEditBody(BaseModel):
    """Whether a subject's class link is paused, from the panel."""

    paused: bool


# CLASS LINKS -----------------------------------------------------------------------------
#
# Each subject's live class link, its teachers' to mint: the administrator sees how full each
# is and can pause or retire one — a link that reached somewhere it should not have.


@router.get("/class-links")
def class_links(db: DbSession = Depends(auth.db)) -> dict:
    """List every live class link: its subject, seats, expiry, pause and who minted it."""
    moment = queries.now()
    return {"class_links": [_class_link(db, link, moment) for link in queries.class_links(db)]}


@router.patch("/class-links/{link_id}")
def pause_class_link(
    link_id: int,
    body: ClassLinkEditBody,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Pause a subject's class link, or resume it."""
    link = _live_class_link(db, link_id)
    queries.edit_class_link(db, link, paused_at=queries.now() if body.paused else None)
    logger.info(
        "[invitaciones] {} ha {} el enlace de clase de «{}»",
        admin.username,
        "pausado" if body.paused else "reanudado",
        link.workspace.slug,
    )
    return {"id": link.id, "paused": body.paused}


@router.delete("/class-links/{link_id}")
def revoke_class_link(
    link_id: int,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    """Retire a subject's class link: it stops working, and whoever entered through it stays."""
    link = _live_class_link(db, link_id)
    queries.revoke_class_link(db, link)
    logger.info("[invitaciones] {} ha retirado el enlace de clase de «{}»", admin.username, link.workspace.slug)
    return {"revoked": link.id}


def _class_link(db: DbSession, link: ClassLink, moment: datetime) -> dict:
    """Render a class link for the panel: its subject and group, how full it is, who minted it."""
    author = queries.get_user_by_id(db, link.created_by) if link.created_by else None
    group = db.get(ClassGroup, link.group_id) if link.group_id is not None else None
    return {
        "id": link.id,
        "workspace": link.workspace.slug,
        "workspace_name": link.workspace.name,
        "group": group.name if group is not None else None,
        "uses": link.uses,
        "max_uses": link.max_uses,
        "expires_at": link.expires_at.isoformat(),
        "expired": link.expires_at <= moment,
        "paused": link.paused_at is not None,
        "created_by": author.username if author else None,
    }


def _live_class_link(db: DbSession, link_id: int) -> ClassLink:
    """Return a class link that has not been retired, or 404."""
    link = db.get(ClassLink, link_id)
    if link is None or link.revoked_at is not None:
        raise HTTPException(404, "Ese enlace de clase no existe.")
    return link
