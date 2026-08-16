"""One ordered stream of everything the system is doing.

Every event carries a monotonic `seq`, so a browser that reloads mid-run reconnects
with `?since=N` and gets back exactly what it missed. Without that, refreshing the
tab during a two-hour build leaves you blind.

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
    """One bus for the process, one `workspace` stamped on every event.

    The stamp used to be a constant the bus read once, because one process served one
    instance. Since phase 3 the publisher says which workspace it is talking about, and
    `visible()` is what keeps a subscriber from ever seeing another instance's tokens.
    An event with no workspace is infrastructure (a job the runner settled before it knew
    whose it was) and reaches everyone; there is deliberately no such publisher on the
    pipeline's own paths.
    """

    def __init__(self, buffer_size: int | None = None):
        self._buffer: deque[Event] = deque(maxlen=buffer_size or settings.EVENT_BUFFER_SIZE)
        self._lock = threading.Lock()
        self._seq = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue] = set()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def last_seq(self) -> int:
        with self._lock:
            return self._seq

    # The forensic record still lives next to the instance it belongs to, so a workspace's
    # `.runs/` holds its own runs and nobody else's — which is also what makes deleting a
    # workspace delete its history.
    def run_dir(self, workspace: str | None) -> Path:
        return Path(settings.workspace_for(workspace).runs_dir)

    # PUBLISH -------------------------------------------------------------------------------

    def publish(
        self,
        workspace: str | None,
        job_id: str | None,
        kind: str,
        payload: dict | None = None,
    ) -> Event:
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
        directory = self.run_dir(workspace)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{job_id}.jsonl"
        with (contextlib.suppress(OSError), path.open("a", encoding="utf-8") as f):
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def _fan_out(self, event: Event) -> None:
        loop = self._loop
        if loop is None or not self._subscribers:
            return
        for queue in list(self._subscribers):
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self._offer, queue, event)

    @staticmethod
    def _offer(queue: asyncio.Queue, event: Event) -> None:
        # A slow consumer must never stall the pipeline: drop the oldest instead.
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(event)

    # REPLAY --------------------------------------------------------------------------------

    def replay(self, since: int = 0, workspace: str | None = None) -> tuple[list[dict], bool]:
        """Buffered events after `since`, plus whether anything was lost to the buffer."""
        with self._lock:
            buffered = list(self._buffer)
        if not buffered:
            return [], False
        gap = since > 0 and buffered[0].seq > since + 1
        return [
            e.to_dict() for e in buffered if e.seq > since and self.visible(e, workspace)
        ], gap

    # The one rule the socket enforces: an event is only delivered to a subscriber whose
    # workspace it belongs to. `workspace=None` means the caller has already established
    # the right to see everything (the CLI, a test), never "the browser asked nicely".
    @staticmethod
    def visible(event: Event, workspace: str | None) -> bool:
        return workspace is None or event.workspace is None or event.workspace == workspace

    def job_events(
        self, workspace: str | None, job_id: str, since: int = 0, limit: int = 5000
    ) -> list[dict]:
        """The full on-disk record for one job — the forensic view, not the live one."""
        path = self.run_dir(workspace) / f"{job_id}.jsonl"
        if not path.is_file():
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
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
