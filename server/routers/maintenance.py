"""The state of the door, readable with no account.

The one route in the API that asks for no session, and that is its whole reason to exist:
the entrance screen has to be able to say «this is under maintenance» before it knows who
is asking. What it returns is what gets shown — the notice and since when — never who
closed it: the panel reads that from `GET /api/admin/maintenance`, which already knows
who is asking.
"""

from fastapi import APIRouter

from ..maintenance import state

router = APIRouter(prefix="/api", tags=["maintenance"])


@router.get("/maintenance")
def read() -> dict:
    current = state()
    return {
        "active": current["active"],
        "message": current["message"],
        "since": current["since"],
    }
