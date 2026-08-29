"""One ordered stream of everything the system is doing.

Every event carries a monotonic `seq`, so a browser that reloads mid-run reconnects with
`?since=N` and gets back exactly what it missed rather than nothing.

Events are published from worker threads and consumed by the asyncio loop serving
WebSockets, so delivery hops threads through `call_soon_threadsafe`.
"""

import asyncio
import contextlib
import json
import threading
import time
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path

from .. import settings
from .models import Event


class EventBus:
    """One bus for the process, with the publisher's `workspace` stamped on every event.

    `visible()` is what keeps a subscriber from ever seeing another instance's tokens. An
    event with no workspace is infrastructure — a job the runner settled before it knew
    whose it was — and reaches everyone; no publisher on the pipeline's own paths is one.
    """

    def __init__(self, buffer_size: int | None = None):
        """Open an empty bus with a replay buffer and no subscribers."""
        self._buffer: deque[Event] = deque(maxlen=buffer_size or settings.EVENT_BUFFER_SIZE)
        self._lock = threading.Lock()
        self._seq = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue] = set()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Adopt the asyncio loop that fan-out has to hop onto."""
        self._loop = loop

    @property
    def last_seq(self) -> int:
        """The sequence number of the last event published."""
        with self._lock:
            return self._seq

    def run_dir(self, workspace: str | None) -> Path | None:
        """Where this workspace's forensic record lives, or `None` when it belongs to none.

        The record sits next to the instance it belongs to, which is also what makes
        deleting a workspace delete its history. An event that is nobody's has no `.runs/`
        to be written into and must not borrow somebody else's.
        """
        if not workspace:
            return None
        return Path(settings.workspace_for(workspace).runs_dir)

    # PUBLISH -------------------------------------------------------------------------------

    def publish(
        self,
        workspace: str | None,
        job_id: str | None,
        kind: str,
        payload: dict | None = None,
    ) -> Event:
        """Number one event, buffer it, file it under its workspace and fan it out."""
        with self._lock:
            self._seq += 1
            event = Event(
                seq=self._seq,
                ts=time.time(),
                job_id=job_id,
                kind=kind,
                payload=payload or {},
                workspace=workspace,
            )
            self._buffer.append(event)

        if job_id:
            self._append_jsonl(workspace, job_id, event)
        self._fan_out(event)
        return event

    def _append_jsonl(self, workspace: str | None, job_id: str, event: Event) -> None:
        """Append one event to its job's on-disk record, if it has anywhere to be written.

        An event with no workspace stays live only: the buffer still has it and the browser
        still sees it. Nothing here may raise — it runs on the runner's thread, and a job
        that cannot write its own log has not failed.
        """
        directory = self.run_dir(workspace)
        if directory is None:
            return
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{job_id}.jsonl"
        with (contextlib.suppress(OSError), path.open("a", encoding="utf-8") as f):
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def _fan_out(self, event: Event) -> None:
        """Hand the event to every subscriber, hopping onto the asyncio loop to do it."""
        loop = self._loop
        if loop is None or not self._subscribers:
            return
        for queue in list(self._subscribers):
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self._offer, queue, event)

    @staticmethod
    def _offer(queue: asyncio.Queue, event: Event) -> None:
        """Put the event on one subscriber's queue, dropping its oldest when it is full.

        A slow consumer must never stall the pipeline.
        """
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(event)

    # REPLAY --------------------------------------------------------------------------------

    def replay(self, since: int = 0, workspace: str | None = None) -> tuple[list[dict], bool]:
        """Return the buffered events after `since`, and whether the buffer lost any of them."""
        with self._lock:
            buffered = list(self._buffer)
        if not buffered:
            return [], False
        gap = since > 0 and buffered[0].seq > since + 1
        return [
            e.to_dict() for e in buffered if e.seq > since and self.visible(e, workspace)
        ], gap

    @staticmethod
    def visible(event: Event, workspace: str | None) -> bool:
        """Whether this subscriber may see this event — the one rule the socket enforces.

        `workspace=None` means the caller has already established the right to see
        everything (the CLI, a test), never that the browser asked nicely.
        """
        return workspace is None or event.workspace is None or event.workspace == workspace

    def job_events(
        self, workspace: str | None, job_id: str, since: int = 0, limit: int = 5000
    ) -> list[dict]:
        """Read one job's full on-disk record — the forensic view, not the live one.

        Falls back to whatever the buffer still holds when the job wrote no file.
        """
        directory = self.run_dir(workspace)
        path = directory / f"{job_id}.jsonl" if directory else None
        if path is None or not path.is_file():
            return [e.to_dict() for e in self._buffer if e.job_id == job_id and e.seq > since]
        out: list[dict] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("seq", 0) > since:
                    out.append(event)
        return out[-limit:]

    # SUBSCRIBE -----------------------------------------------------------------------------

    @contextlib.asynccontextmanager
    async def subscribe(self, maxsize: int = 2000) -> AsyncIterator[asyncio.Queue]:
        """Lend a queue that receives every event published while the block is open."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
