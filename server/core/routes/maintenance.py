"""The state of the door, readable with no account.

The one router that declares no authorisation at all, and that is its whole reason to
exist: the entrance screen has to say "this is under maintenance" before it knows who is
asking. It answers the notice and since when, never who closed it — the panel reads that
from `GET /api/admin/maintenance`, which is behind `require_admin`.
"""

from fastapi import APIRouter

from ..maintenance import state

router = APIRouter(prefix="/api", tags=["maintenance"])


@router.get("/maintenance")
def read() -> dict:
    """Answer whether the installation is closed, with what notice and since when."""
    current = state()
    return {
        "active": current["active"],
        "message": current["message"],
        "since": current["since"],
    }
