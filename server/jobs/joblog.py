"""The job log on disk, `logs/<slug>/jobs.log`: no screen shows a run's loguru output.

**One sink per WORKSPACE, shared by every job of it.** A lane with room runs several jobs
at once, and two loguru file sinks on one path would each own a handle and each try to
rotate it. The sink is opened by the first job of a workspace and closed when the last one
leaves.

**Filtering by THREAD is what keeps two workspaces apart.** The core logs with loguru and
knows nothing about jobs, so the thread a record was emitted on is the only thing that says
whose log it is.

The build worker writes into the same file from its own process; appends are line-atomic,
and the only thing the two writers can race on is a rotation, which costs a few lines.
"""

import threading
from pathlib import Path

from loguru import logger

from variatio import config
from variatio.core import paths

FILE_NAME = "jobs.log"
FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module} >> {message}"
ROTATION = "5 MB"
RETENTION = 5


def path_for(slug: str) -> Path:
    """Return the job log of one workspace, creating its directory."""
    return paths.workspace_logs_dir(slug) / FILE_NAME


class _Open:
    """One workspace's live sink and the job threads writing through it."""

    def __init__(self) -> None:
        """Start with no sink and nobody writing."""
        self.threads: set[int] = set()
        self.sink_id: int | None = None


_lock = threading.Lock()
_open: dict[str, _Open] = {}


def attach(slug: str) -> None:
    """Send this thread's loguru output to `slug`'s job log until `detach`.

    A job with no workspace writes nowhere rather than raising: this is a mirror, and it
    must never be the reason a job fails.
    """
    if not slug:
        return
    thread_id = threading.get_ident()
    with _lock:
        entry = _open.setdefault(slug, _Open())
        entry.threads.add(thread_id)
        if entry.sink_id is None:
            entry.sink_id = _add(slug, entry.threads)


def detach(slug: str) -> None:
    """Stop mirroring this thread, closing the file once the last job of `slug` is done."""
    if not slug:
        return
    thread_id = threading.get_ident()
    with _lock:
        entry = _open.get(slug)
        if entry is None:
            return
        entry.threads.discard(thread_id)
        if entry.threads:
            return
        sink_id = entry.sink_id
        del _open[slug]
    if sink_id is not None:
        logger.remove(sink_id)


def _add(slug: str, threads: set[int]) -> int | None:
    """Open the file sink of one workspace, or warn and return None if it cannot be opened."""
    try:
        target = path_for(slug)
    except (OSError, ValueError) as exc:
        logger.warning(f"No se pudo abrir el registro de «{slug}»: {exc}")
        return None
    # `threads` is the live set, not a copy: a second job of the same workspace joins the
    # sink that is already open instead of opening one of its own.
    return logger.add(
        target,
        level=config.LOG_LEVEL,
        format=FORMAT,
        rotation=ROTATION,
        retention=RETENTION,
        encoding="utf-8",
        filter=lambda record: record["thread"].id in threads,
    )
