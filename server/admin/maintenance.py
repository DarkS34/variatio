"""The installation's door, from the panel: closing it for maintenance and opening it again.

Behind `require_admin`, under `/api/admin` like every route of the panel. Who closed it is read here; the entrance screen reads only that it is
closed (`core/routes/maintenance.py`).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import auth
from ..core import maintenance
from ..db.models import User

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class MaintenanceBody(BaseModel):
    """Whether the door is shut, and the notice shown while it is."""

    active: bool
    message: str | None = None


# THE DOOR --------------------------------------------------------------------------------


@router.get("/maintenance")
def read_maintenance() -> dict:
    """Answer the door's state with who closed it, which the public route withholds."""
    return maintenance.state()


@router.post("/maintenance")
def set_maintenance(
    body: MaintenanceBody, admin: User = Depends(auth.require_admin)
) -> dict:
    """Open or shut the installation. Written here and nowhere else.

    Reading it does NOT go through here: `GET /api/maintenance` asks for no session,
    because the notice has to reach whoever has not got in yet.
    """
    return maintenance.set_state(body.active, body.message, admin.username)
