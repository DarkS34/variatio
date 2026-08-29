"""As many jobs at once as each backend has room for, in order.

Not one queue: Ollama serves from a single GPU, so two local jobs would do nothing but swap
weights, while Cerebras serves over the network. Between the two there is no contention at
all, and a single queue made every job wait for a machine it was never going to use.

Nor one job per lane. That was the first shape of this, and it was right about the GPU and
wrong about the quota: two remote jobs contend for a rolling budget, and that budget is
already administered call by call by `core/cerebras_budget`, which books each call's room
before it goes out. Serialising the lane on top of that bought nothing and cost the thing
people actually noticed — two people could not work at the same time. So a lane has a
CAPACITY (`lanes.capacity`): one locally and always, `CEREBRAS_MAX_CONCURRENT_JOBS`
remotely.

A job reserves the lanes of the generative models it calls (`jobs/lanes.py`) and runs as
soon as every one of them has a free slot. Within a lane the order of arrival is kept, and
a job that cannot start holds a slot of each of its lanes against everything behind it —
otherwise a job needing both would never get them. A job that calls no model reserves
nothing and never waits.
"""

import subprocess
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager

from loguru import logger

from variatio import config
from variatio.core import progress

from . import lanes
from .bus import EventBus
from .models import SUBPROCESS_KINDS, Job

Handler = Callable[[Job, "JobControl"], "dict | None"]

_DISPATCH_TICK_SECONDS = 0.5


class JobControl:
    """The emitter the core writes to, and the handle the API cancels through."""

    def __init__(self, bus: EventBus, job: Job):
        self._bus = bus
        self.job = job
        self.cancel_event = threading.Event()
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._logs_muted = False

    # progress.Emitter protocol
    def emit(self, kind: str, payload: dict) -> None:
        self._bus.publish(self.job.workspace, self.job.id, kind, payload)

    def should_cancel(self) -> bool:
        return self.cancel_event.is_set()

    # The loguru mirror does NOT go through the progress emitter, so a job that filters
    # its events cannot filter its logs: the blind evaluation would still publish
    # "few-shot seleccionado" and give away which proposal is the system's. Muted at the
    # source; stderr and the log file keep everything, so the developer loses nothing.
    @property
    def logs_muted(self) -> bool:
        return self._logs_muted

    @contextmanager
    def muted_logs(self):
        self._logs_muted = True
        try:
            yield
        finally:
            self._logs_muted = False

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
        # What gets enqueued by itself when a job finishes well. The queue stays generic: who
        # follows whom is decided by `jobs/chain.py`, which `runtime.py` installs.
        self.after_success: Callable[["JobRunner", Job], None] | None = None
        self._jobs: dict[str, Job] = {}
        self._controls: dict[str, JobControl] = {}
        self._order: list[str] = []
        # Which jobs hold each backend right now, oldest first. A lane with an empty list
        # is free; a running job that reserves nothing appears in neither.
        self._holders: dict[str, list[str]] = {}
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._wake = threading.Event()
        self._last_activity = time.time()

    # LIFECYCLE -----------------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._dispatch, name="job-dispatch", daemon=True)
        self._thread.start()

    def shutdown(self, timeout: float = 5.0) -> None:
        self._stopping.set()
        with self._lock:
            controls = [self._controls[j.id] for j in self._running_locked()]
        for control in controls:
            control.request_cancel()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    # API -----------------------------------------------------------------------------------

    def submit(
        self,
        kind: str,
        params: dict | None = None,
        workspace: str = "",
        user_id: int | None = None,
        user_name: str | None = None,
    ) -> Job:
        if kind not in self.handlers:
            raise ValueError(f"Unknown job kind '{kind}'")
        job = Job(
            kind=kind,
            params=params or {},
            workspace=workspace,
            user_id=user_id,
            user_name=user_name,
        )
        # Resolved here rather than at dispatch: the engine can be switched from the panel
        # mid-queue, and a job has to wait for the lanes it was accepted against.
        job.backends = sorted(lanes.backends_for(kind, job.params))
        with self._lock:
            self._jobs[job.id] = job
            self._controls[job.id] = JobControl(self.bus, job)
            self._order.append(job.id)
            self._last_activity = time.time()
            self._restamp()
        self.bus.publish(job.workspace, job.id, "job.queued", {"job": job.to_dict()})
        self._wake.set()
        return job

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            control = self._controls.get(job_id)
            if job is None:
                return False
            if job.status == "queued":
                job.status = "cancelled"
                job.queue_position = 0
                job.finished_at = time.time()
                self._restamp()
                self.bus.publish(
                    job.workspace, job_id, "job.cancelled", {"job": job.to_dict()}
                )
                self._wake.set()
                return True
            if job.status != "running" or control is None:
                return False
        control.request_cancel()
        self.bus.publish(job.workspace, job_id, "job.cancelling", {})
        return True

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    # Every listing narrows by workspace, and `None` means "the whole queue" — used only
    # where the caller has already established the right to see it. The machine is shared, so
    # "something is running" is legitimately global; *what* is running is not.
    def all(self, limit: int = 50, workspace: str | None = None) -> list[Job]:
        with self._lock:
            jobs = [self._jobs[i] for i in self._order]
        if workspace is not None:
            jobs = [j for j in jobs if j.workspace == workspace]
        return jobs[-limit:][::-1]

    def running(self, workspace: str | None = None) -> list[Job]:
        with self._lock:
            jobs = self._running_locked()
        if workspace is not None:
            jobs = [j for j in jobs if j.workspace == workspace]
        return jobs

    # The oldest job still running. Kept because a caller that only asks «is the machine
    # doing something, and what» has one honest answer and does not want a list.
    def current(self) -> Job | None:
        jobs = self.running()
        if not jobs:
            return None
        return min(jobs, key=lambda j: (j.started_at or j.created_at))

    # The oldest job holding this lane. Kept as the one-line answer to «what is this half
    # of the engine doing», which is what a label needs; `holders_in` is the honest count.
    def current_in(self, backend: str) -> Job | None:
        holders = self.holders_in(backend)
        return holders[0] if holders else None

    def holders_in(self, backend: str) -> list[Job]:
        with self._lock:
            return [
                self._jobs[i] for i in self._holders.get(backend, ()) if i in self._jobs
            ]

    def pending(self, workspace: str | None = None) -> list[Job]:
        with self._lock:
            jobs = [self._jobs[i] for i in self._order]
        return [
            j
            for j in jobs
            if j.status == "queued" and (workspace is None or j.workspace == workspace)
        ]

    # Where in ITS OWN lane a job is, counting from 1, or 0 when it is already running.
    # What is ahead of a job is only what could be holding a lane it needs, so a remote job
    # queued behind an hour of local building reports 1 and starts at once.
    def queue_position(self, job_id: str) -> int:
        with self._lock:
            return self._position(job_id)

    def building_artifacts(self, workspace: str | None = None) -> set[str]:
        """Artifacts a running or queued job is about to (re)write, in this workspace."""
        with self._lock:
            active = [j for j in self._jobs.values() if j.status in ("running", "queued")]
        return {
            j.artifact
            for j in active
            if j.artifact and (workspace is None or j.workspace == workspace)
        }

    def is_busy(self) -> bool:
        with self._lock:
            return bool(self._running_locked()) or bool(self.pending())

    # Seconds since the last job enqueued or finished, counting EVERY lane. It is the only
    # measure of idleness that exists here, and it is enough: everything this process asks a
    # model for goes through the queue, so «nobody has asked for anything» and «the GPU is
    # not needed» are the same thing. Returns 0 while anything runs or waits.
    #
    # Deliberately not narrowed to the local lane. A job that reserves only `remote` still
    # embeds and still screens with the guardrail, and those two are exactly the models the
    # lane calculation leaves out — so «no local lane reserved» is not «the GPU is free»,
    # and releasing it under a remote job would unload the embedder that job is calling.
    def idle_seconds(self) -> float:
        with self._lock:
            if self._running_locked() or self.pending():
                return 0.0
            return max(0.0, time.time() - self._last_activity)

    # INTERNAL STATE ------------------------------------------------------------------------

    def _running_locked(self) -> list[Job]:
        return [self._jobs[i] for i in self._order if self._jobs[i].status == "running"]

    def _position(self, job_id: str) -> int:
        job = self._jobs.get(job_id)
        if job is None or job.status != "queued":
            return 0
        mine = set(job.backends)
        position = 1
        for other_id in self._order:
            if other_id == job_id:
                break
            other = self._jobs[other_id]
            if other.status == "queued" and mine & set(other.backends):
                position += 1
        return position

    def _restamp(self) -> None:
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.status == "queued":
                job.queue_position = self._position(job_id)

    # WORKER --------------------------------------------------------------------------------

    def _dispatch(self) -> None:
        while not self._stopping.is_set():
            self._wake.wait(_DISPATCH_TICK_SECONDS)
            self._wake.clear()
            if self._stopping.is_set():
                return
            self._launch_ready()

    # FIFO over the whole queue, skipping what cannot start. A blocked job TAKES A SLOT of
    # each of its lanes for the rest of the pass so nothing behind it takes that slot:
    # without it, a job needing both lanes would be overtaken for ever by single-lane jobs
    # arriving after it. At capacity 1 this is exactly the old set of claimed lanes.
    #
    # Capacity is read once per pass, live from the configuration: the panel changes it
    # while the process runs, and the job that starts next is the one to honour it.
    def _launch_ready(self) -> None:
        while True:
            caps = lanes.capacities()
            with self._lock:
                taken = {b: len(ids) for b, ids in self._holders.items()}
                chosen: tuple[Job, JobControl] | None = None
                for job_id in self._order:
                    job = self._jobs[job_id]
                    if job.status != "queued":
                        continue
                    reserved = set(job.backends)
                    if any(taken.get(b, 0) >= caps.get(b, 1) for b in reserved):
                        for backend in reserved:
                            taken[backend] = taken.get(backend, 0) + 1
                        continue
                    chosen = (job, self._controls[job_id])
                    break
                if chosen is None:
                    return
                job, control = chosen
                job.status = "running"
                job.started_at = time.time()
                job.queue_position = 0
                for backend in job.backends:
                    self._holders.setdefault(backend, []).append(job.id)
                self._restamp()

            threading.Thread(
                target=self._execute,
                args=(job, control),
                name=f"job-{job.id}",
                daemon=True,
            ).start()

    def _execute(self, job: Job, control: JobControl) -> None:
        self.bus.publish(job.workspace, job.id, "job.started", {"job": job.to_dict()})
        sink_id = self._attach_log_sink(control)
        token = progress.set_emitter(control)
        try:
            result = self.handlers[job.kind](job, control)
            if control.should_cancel():
                self._settle(job, "cancelled")
            else:
                job.result = result
                self._settle(job, "succeeded")
                self._chain(job)
        except progress.Cancelled:
            self._settle(job, "cancelled")
        except Exception as exc:  # noqa: BLE001 - reported to the UI, never swallowed
            logger.exception(f"El trabajo «{job.kind}» falló")
            job.error = f"{type(exc).__name__}: {exc}"
            self._settle(job, "failed")
        finally:
            progress.reset_emitter(token)
            logger.remove(sink_id)
            self._release(job)

    def _release(self, job: Job) -> None:
        with self._lock:
            for backend in job.backends:
                holders = self._holders.get(backend)
                if holders and job.id in holders:
                    holders.remove(job.id)
                if holders is not None and not holders:
                    del self._holders[backend]
            self._restamp()
        self._wake.set()

    # Chaining is a convenience, not part of the result: if it fails, the job that just
    # finished is still finished and only the next link is lost.
    def _chain(self, job: Job) -> None:
        if self.after_success is None:
            return
        try:
            self.after_success(self, job)
        except Exception as exc:  # noqa: BLE001 - el trabajo ya terminó bien
            logger.warning(f"No se pudo encadenar nada tras «{job.label}»: {exc}")

    def _settle(self, job: Job, status: str) -> None:
        job.status = status
        job.queue_position = 0
        job.finished_at = time.time()
        with self._lock:
            self._last_activity = job.finished_at
        kind = {
            "succeeded": "job.finished",
            "failed": "job.failed",
            "cancelled": "job.cancelled",
        }[status]
        self.bus.publish(job.workspace, job.id, kind, {"job": job.to_dict()})

    # The core logs with loguru and knows nothing about us. Mirroring its output into
    # the stream gives the UI a raw console for free — no changes to the pipeline.
    #
    # The filter is what keeps two concurrent jobs from writing into each other's drawer:
    # each job runs on its own thread, so each sink only ever sees the records of the one
    # it was attached for.
    def _attach_log_sink(self, control: JobControl) -> int:
        worker_id = threading.get_ident()

        def sink(message) -> None:
            if control.logs_muted:
                return
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
            level=config.LOG_LEVEL,
            format="{message}",
            filter=lambda r: r["thread"].id == worker_id,
        )


def uses_subprocess(kind: str) -> bool:
    return kind in SUBPROCESS_KINDS
