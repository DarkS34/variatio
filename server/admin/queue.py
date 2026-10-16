"""The queue as the panel shows it: what holds each lane, and cancelling a job.

Behind `require_admin`, under `/api/admin` like every route of the panel.
"""

from fastapi import APIRouter, Depends, HTTPException

from .. import auth
from ..core import process
from .shared import _lane_jobs

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


# THE QUEUE -------------------------------------------------------------------------------


@router.get("/jobs")
def job_queue() -> dict:
    """Answer the queue of the whole installation, lane by lane.

    `running` is the oldest job, kept as it was; `lanes` is the honest picture now that
    the queue serialises per backend and two jobs can be in flight at once.
    """
    running = process.runner.running()
    return {
        "running": running[0].to_dict() if running else None,
        "lanes": _lane_jobs(),
        "queued": [
            {**job.to_dict(), "queue_position": process.runner.queue_position(job.id)}
            for job in process.runner.pending()
        ],
    }


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str) -> dict:
    """Cancel any job of the installation, whatever workspace it belongs to."""
    if process.runner.get(job_id) is None:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'.")
    return {"cancelled": process.runner.cancel(job_id)}
