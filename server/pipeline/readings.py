"""What the chain reads off the live queue: what is building, what is being transcribed, and
the state of the whole chain.

Each one reads the queue through `core.process` when called, so a test that puts its own
runner there is the one they see.
"""

from variatio.core.workspace import Workspace

from ..core import process
from . import chain, slots
from .approvals import EXEMPLARS_BANK, Approvals


def pipeline_snapshot(ws: Workspace) -> list[dict]:
    """The whole chain's state for one workspace, with what is building marked as such."""
    return approvals(ws).snapshot(building(ws))


def building(ws: Workspace) -> set[str]:
    """The artifacts a job is building right now in one workspace.

    The bank counts from the moment its collection starts, which is the taggability review
    at the head of its chain (`chain.py`): the review writes no bank, but a screen that read
    the bank as missing meanwhile would offer to collect it a second time.
    """
    artifacts = process.runner.building_artifacts(ws.slug)
    for job in process.runner.running(ws.slug) + process.runner.pending(ws.slug):
        if job.kind == "review_taggability" and "build_bank" in chain.remaining(job):
            artifacts.add(EXEMPLARS_BANK)
    return artifacts


def transcribing(slug: str, slot: str):
    """Find one slot's transcription job, running or waiting, or nothing.

    Reads `running(slug)` and not `current()`: with two lanes there is more than one job
    at a time and `current()` only answers the oldest, so a transcription on the other
    lane would slip past. A WAITING one counts too — it is about to write the same page
    cache a build of that slot would read and write.
    """
    for job in process.runner.running(slug) + process.runner.pending(slug):
        if job.kind == slots.TRANSCRIBE_JOB and job.params.get("slot") == slot:
            return job
    return None


def approvals(ws: Workspace) -> Approvals:
    """Return a fresh `Approvals` reader for one workspace."""
    return Approvals(ws)
