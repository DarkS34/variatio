"""One job at a time, in order.

Not a limitation to be lifted later: Ollama serves these from a single GPU, and
running a 35B extraction next to a 31B tagger would do nothing but swap weights.
The queue makes the contention explicit instead of accidental.
"""

import queue
import subprocess
import threading
import time
from collections.abc import Callable

from loguru import logger

from variant_generator import progress

from .bus import EventBus
from .models import SUBPROCESS_KINDS, Job

Handler = Callable[[Job, "JobControl"], "dict | None"]


class JobControl:
    """The emitter the core writes to, and the handle the API cancels through."""

    def __init__(self, bus: EventBus, job: Job):
        self._bus = bus
        self.job = job
        self.cancel_event = threading.Event()
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    # progress.Emitter protocol
    def emit(self, kind: str, payload: dict) -> None:
        self._bus.publish(self.job.id, kind, payload)

    def should_cancel(self) -> bool:
        return self.cancel_event.is_set()

    def attach_process(self, process: subprocess.Popen) -> None:
        with self._lock:
            self._process = process
            if self.cancel_event.is_set():
                self._kill()

    def request_cancel(self) -> None:
        self.cancel_event.set()
        with self._lock:
            self._kill()

    def _kill(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


class JobRunner:
    def __init__(self, bus: EventBus, handlers: dict[str, Handler]):
        self.bus = bus
        self.handlers = handlers
        self._queue: queue.Queue[str] = queue.Queue()
        self._jobs: dict[str, Job] = {}
        self._controls: dict[str, JobControl] = {}
        self._order: list[str] = []
        self._current: str | None = None
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()

    # LIFECYCLE -----------------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="job-runner", daemon=True)
        self._thread.start()

    def shutdown(self, timeout: float = 5.0) -> None:
        self._stopping.set()
        with self._lock:
            current = self._controls.get(self._current) if self._current else None
        if current is not None:
            current.request_cancel()
        self._queue.put("")
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    # API -----------------------------------------------------------------------------------

    def submit(self, kind: str, params: dict | None = None) -> Job:
        if kind not in self.handlers:
            raise ValueError(f"Unknown job kind '{kind}'")
        job = Job(kind=kind, params=params or {})
        with self._lock:
            self._jobs[job.id] = job
            self._controls[job.id] = JobControl(self.bus, job)
            self._order.append(job.id)
        self.bus.publish(job.id, "job.queued", {"job": job.to_dict()})
        self._queue.put(job.id)
        return job

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            control = self._controls.get(job_id)
            if job is None:
                return False
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = time.time()
                self.bus.publish(job_id, "job.cancelled", {"job": job.to_dict()})
                return True
            if job.status != "running" or control is None:
                return False
        control.request_cancel()
        self.bus.publish(job_id, "job.cancelling", {})
        return True

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self, limit: int = 50) -> list[Job]:
        with self._lock:
            return [self._jobs[i] for i in self._order[-limit:]][::-1]

    def current(self) -> Job | None:
        with self._lock:
            return self._jobs.get(self._current) if self._current else None

    def pending(self) -> list[Job]:
        with self._lock:
            return [j for j in (self._jobs[i] for i in self._order) if j.status == "queued"]

    def building_artifacts(self) -> set[str]:
        """Artifacts a running or queued job is about to (re)write."""
        with self._lock:
            active = [
                j for j in self._jobs.values() if j.status in ("running", "queued")
            ]
        return {j.artifact for j in active if j.artifact}

    def is_busy(self) -> bool:
        with self._lock:
            return self._current is not None or bool(self.pending())

    # WORKER --------------------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stopping.is_set():
            job_id = self._queue.get()
            if not job_id:
                continue
            with self._lock:
                job = self._jobs.get(job_id)
                control = self._controls.get(job_id)
            if job is None or control is None or job.status != "queued":
                continue
            self._execute(job, control)

    def _execute(self, job: Job, control: JobControl) -> None:
        with self._lock:
            self._current = job.id
            job.status = "running"
            job.started_at = time.time()

        self.bus.publish(job.id, "job.started", {"job": job.to_dict()})
        sink_id = self._attach_log_sink(control)
        token = progress.set_emitter(control)
        try:
            result = self.handlers[job.kind](job, control)
            if control.should_cancel():
                self._settle(job, "cancelled")
            else:
                job.result = result
                self._settle(job, "succeeded")
        except progress.Cancelled:
            self._settle(job, "cancelled")
        except Exception as exc:  # noqa: BLE001 - reported to the UI, never swallowed
            logger.exception(f"Job {job.kind} failed")
            job.error = f"{type(exc).__name__}: {exc}"
            self._settle(job, "failed")
        finally:
            progress.reset_emitter(token)
            logger.remove(sink_id)
            with self._lock:
                self._current = None

    def _settle(self, job: Job, status: str) -> None:
        job.status = status
        job.finished_at = time.time()
        kind = {
            "succeeded": "job.finished",
            "failed": "job.failed",
            "cancelled": "job.cancelled",
        }[status]
        self.bus.publish(job.id, kind, {"job": job.to_dict()})

    # The core logs with loguru and knows nothing about us. Mirroring its output into
    # the stream gives the UI a raw console for free — no changes to the pipeline.
    def _attach_log_sink(self, control: JobControl) -> int:
        worker_id = threading.get_ident()

        def sink(message) -> None:
            record = message.record
            control.emit(
                "log",
                {
                    "level": record["level"].name,
                    "module": record["module"],
                    "message": record["message"],
                },
            )

        return logger.add(
            sink,
            level="DEBUG",
            format="{message}",
            filter=lambda r: r["thread"].id == worker_id,
        )


def uses_subprocess(kind: str) -> bool:
    return kind in SUBPROCESS_KINDS
