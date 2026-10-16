"""What two of the panel's route modules share: what is holding each lane of the queue.

A route module imports no other (an import contract), so the overview and the queue tab read
it from here.
"""

from ..core import process
from ..jobs import lanes as jobs_lanes


def _lane_jobs() -> dict:
    """Report what is holding each lane, as a list and with the room it is filling.

    A list per lane and not one job: the remote lane holds as many as
    `CEREBRAS_MAX_CONCURRENT_JOBS` allows, so the oldest of them does not answer "what is
    this half of the engine doing", and N jobs means nothing without the capacity.
    """
    return {
        backend: {
            "capacity": jobs_lanes.capacity(backend),
            "jobs": [job.to_dict() for job in process.runner.holders_in(backend)],
        }
        for backend in jobs_lanes.BACKENDS
    }
