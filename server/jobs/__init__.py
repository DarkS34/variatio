"""The job queue: what runs, on which backend, in what order, and who hears about it."""

# `handlers` is imported for its registrations: the construction's kinds join `HANDLERS`.
from . import chain, handlers, lanes
from .bus import EventBus
from .catalogue import HANDLERS, JOB_LABELS, SUBPROCESS_KINDS, Event, Job
from .idle import IdleUnloader, release_gpu
from .lanes import LOCAL, REMOTE, backends_for
from .runner import JobControl, JobRunner

__all__ = [
    "HANDLERS",
    "LOCAL",
    "REMOTE",
    "backends_for",
    "chain",
    "lanes",
    "IdleUnloader",
    "release_gpu",
    "JOB_LABELS",
    "SUBPROCESS_KINDS",
    "Event",
    "EventBus",
    "Job",
    "JobControl",
    "JobRunner",
]
