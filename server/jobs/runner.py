"""As many jobs at once as each backend has room for, in order.

Not one queue: Ollama serves from a single GPU while Cerebras serves over the network, and
between the two there is no contention at all — one queue made every job wait for a machine
it was never going to use. Nor one job per lane: a lane has a CAPACITY (`lanes.capacity`),
one locally and always, `CEREBRAS_MAX_CONCURRENT_JOBS` remotely, because what is scarce
remotely is a rolling budget that `core/cerebras_budget` already books call by call.

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

from loguru import logger

from variatio.core import progress

from . import joblog, lanes
from .bus import EventBus
from .catalogue import SUBPROCESS_KINDS, Job

Handler = Callable[[Job, "JobControl"], "dict | None"]

_DISPATCH_TICK_SECONDS = 0.5

# What a terminated child is given to leave on its own before the choice is taken away.
# It is spent on another thread, never inside the request that asked for the stop.
_TERMINATE_GRACE_SECONDS = 5.0


class JobControl:
    """The emitter the core writes to, and the handle the API cancels through."""

    def __init__(self, bus: EventBus, job: Job):
        """Bind one job to the bus it publishes on."""
        self._bus = bus
        self.job = job
        self.cancel_event = threading.Event()
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    # progress.Emitter protocol
    def emit(self, kind: str, payload: dict) -> None:
        """Publish one event of this job, stamped with its workspace."""
        self._bus.publish(self.job.workspace, self.job.id, kind, payload)

    def should_cancel(self) -> bool:
        """Whether somebody has asked this job to stop."""
        return self.cancel_event.is_set()

    def attach_process(self, process: subprocess.Popen) -> None:
        """Adopt the subprocess a handler spawned, killing it at once if cancel already came."""
        with self._lock:
            self._process = process
            if self.cancel_event.is_set():
                self._kill()

    def request_cancel(self) -> None:
        """Ask the job to stop: raise the flag and kill any subprocess it holds.

        It RETURNS AT ONCE, and that is the point: this runs on the thread serving
        `DELETE /api/jobs/{id}`, and the escalation below waits five seconds for a child
        that is never going to answer in one — the worker's SIGTERM handler only raises its
        own cancel flag, so it leaves at its next checkpoint or not at all. Waiting for it
        here spent those five seconds inside the request, so the screen could not even say
        the stop had been heard until they were over.
        """
        self.cancel_event.set()
        with self._lock:
            self._kill()

    def _kill(self) -> None:
        """Terminate the attached subprocess, escalating to a kill on another thread."""
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        threading.Thread(
            target=self._escalate, args=(process,), name="job-kill", daemon=True
        ).start()

    @staticmethod
    def _escalate(process: subprocess.Popen) -> None:
        """Give a terminated child its grace period, then take the choice away."""
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()


class JobRunner:
    """The queue itself: one dispatch thread, one worker thread per running job."""

    def __init__(self, bus: EventBus, handlers: dict[str, Handler]):
        """Build an idle runner; `start()` is what puts the dispatch thread on the road."""
        self.bus = bus
        self.handlers = handlers
        # Enqueued by itself when a job finishes well. The queue stays generic: who follows
        # whom is `jobs/chain.py`'s, installed by `singletons.py`.
        self.after_success: Callable[["JobRunner", Job], None] | None = None
        self._jobs: dict[str, Job] = {}
        self._controls: dict[str, JobControl] = {}
        self._order: list[str] = []
        # Which jobs hold each backend, oldest first. An empty list is a free lane; a job
        # that reserves nothing appears in neither.
        self._holders: dict[str, list[str]] = {}
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._wake = threading.Event()
        self._last_activity = time.time()

    # LIFECYCLE -----------------------------------------------------------------------------

    def start(self) -> None:
        """Start the dispatch thread, once."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._dispatch, name="job-dispatch", daemon=True)
        self._thread.start()

    def shutdown(self, timeout: float = 5.0) -> None:
        """Cancel everything running and wait for the dispatch thread to leave."""
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
        """Queue one job and announce it. Raises ValueError for a kind nobody handles."""
        if kind not in self.handlers:
            raise ValueError(f"Unknown job kind '{kind}'")
        job = Job(
            kind=kind,
            params=params or {},
            workspace=workspace,
            user_id=user_id,
            user_name=user_name,
        )
        # Resolved on submit rather than on dispatch: the engine can be switched from the
        # panel mid-queue, and a job waits for the lanes it was accepted against.
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
        """Drop a queued job or ask a running one to stop; False if there is nothing to stop."""
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
        """Return one job by id, whatever its state, or `None`."""
        with self._lock:
            return self._jobs.get(job_id)

    def all(self, limit: int = 50, workspace: str | None = None) -> list[Job]:
        """Return the last `limit` jobs, newest first.

        As in every listing here, `workspace=None` means the whole queue and is for callers
        that have already established the right to see it. The machine is shared, so "is
        something running" is legitimately global; *what* is running is not.
        """
        with self._lock:
            jobs = [self._jobs[i] for i in self._order]
        if workspace is not None:
            jobs = [j for j in jobs if j.workspace == workspace]
        return jobs[-limit:][::-1]

    def current(self) -> Job | None:
        """Return the oldest job still running — the one honest answer to "what is it doing"."""
        jobs = self.running()
        if not jobs:
            return None
        return min(jobs, key=lambda j: (j.started_at or j.created_at))

    def running(self, workspace: str | None = None) -> list[Job]:
        """Return every job running right now, in order of arrival."""
        with self._lock:
            jobs = self._running_locked()
        if workspace is not None:
            jobs = [j for j in jobs if j.workspace == workspace]
        return jobs

    def current_in(self, backend: str) -> Job | None:
        """Return the oldest job holding this lane, for a label. `holders_in` is the count."""
        holders = self.holders_in(backend)
        return holders[0] if holders else None

    def holders_in(self, backend: str) -> list[Job]:
        """Return every job holding a slot of this lane, oldest first."""
        with self._lock:
            return [
                self._jobs[i] for i in self._holders.get(backend, ()) if i in self._jobs
            ]

    def queue_position(self, job_id: str) -> int:
        """Say where a job stands in ITS OWN lanes, from 1, or 0 once it is running.

        What is ahead of a job is only what could hold a lane it needs, so a remote job
        queued behind an hour of local building reports 1 and starts at once.
        """
        with self._lock:
            return self._position(job_id)

    def building_artifacts(self, workspace: str | None = None) -> set[str]:
        """Return the artifacts a running or queued job is about to (re)write here."""
        with self._lock:
            active = [j for j in self._jobs.values() if j.status in ("running", "queued")]
        return {
            j.artifact
            for j in active
            if j.artifact and (workspace is None or j.workspace == workspace)
        }

    def is_busy(self) -> bool:
        """Whether anything is running or waiting, anywhere in the installation."""
        with self._lock:
            return bool(self._running_locked()) or bool(self.pending())

    def idle_seconds(self) -> float:
        """Return the seconds since the last job was queued or finished; 0 while any is alive.

        The only measure of idleness there is, and enough: every model call of this process
        goes through the queue, so "nobody has asked for anything" and "the GPU is not
        needed" are the same statement.

        It counts EVERY lane and is deliberately not narrowed to the local one. A job
        reserving only `remote` still embeds and still screens with the guardrail — the two
        models the lane calculation leaves out — so releasing the GPU under it would unload
        what it is calling.
        """
        with self._lock:
            if self._running_locked() or self.pending():
                return 0.0
            return max(0.0, time.time() - self._last_activity)

    def pending(self, workspace: str | None = None) -> list[Job]:
        """Return every job still waiting for a lane, in order of arrival."""
        with self._lock:
            jobs = [self._jobs[i] for i in self._order]
        return [
            j
            for j in jobs
            if j.status == "queued" and (workspace is None or j.workspace == workspace)
        ]

    # INTERNAL STATE ------------------------------------------------------------------------

    def _running_locked(self) -> list[Job]:
        """Return every running job, in order of arrival. The caller holds the lock."""
        return [self._jobs[i] for i in self._order if self._jobs[i].status == "running"]

    def _restamp(self) -> None:
        """Re-derive every queued job's position after the queue moved. Lock held."""
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.status == "queued":
                job.queue_position = self._position(job_id)

    def _position(self, job_id: str) -> int:
        """Count the queued jobs ahead of this one sharing a lane with it. Lock held."""
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

    # WORKER --------------------------------------------------------------------------------

    def _dispatch(self) -> None:
        """Wake on every change (and every half second) and start whatever can start."""
        while not self._stopping.is_set():
            self._wake.wait(_DISPATCH_TICK_SECONDS)
            self._wake.clear()
            if self._stopping.is_set():
                return
            self._launch_ready()

    def _launch_ready(self) -> None:
        """Start every job whose lanes have room, one worker thread each.

        Capacity is read once per pass, live from the configuration: the panel changes it
        while the process runs, and the job that starts next is the one to honour it.
        """
        while True:
            caps = lanes.capacities()
            with self._lock:
                job_id = self._next_ready(caps)
                if job_id is None:
                    return
                job = self._jobs[job_id]
                control = self._controls[job_id]
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

    def _next_ready(self, caps: dict[str, int]) -> str | None:
        """FIFO over the queue, skipping what cannot start. The caller holds the lock.

        A blocked job TAKES A SLOT of each of its lanes for the rest of the pass, so nothing
        behind it takes that slot: without this a job needing both lanes would be overtaken
        for ever by single-lane jobs arriving after it.
        """
        taken = {b: len(ids) for b, ids in self._holders.items()}
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.status != "queued":
                continue
            reserved = set(job.backends)
            if any(taken.get(b, 0) >= caps.get(b, 1) for b in reserved):
                for backend in reserved:
                    taken[backend] = taken.get(backend, 0) + 1
                continue
            return job_id
        return None

    def _execute(self, job: Job, control: JobControl) -> None:
        """Run one job to its end on its own thread, releasing its lanes whatever happens."""
        self.bus.publish(job.workspace, job.id, "job.started", {"job": job.to_dict()})
        joblog.attach(job.workspace)
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
            code = getattr(exc, "code", None)
            job.error_code = code if isinstance(code, str) else None
            self._settle(job, "failed")
        finally:
            progress.reset_emitter(token)
            joblog.detach(job.workspace)
            self._release(job)

    def _release(self, job: Job) -> None:
        """Give back every lane slot this job held and wake the dispatcher."""
        with self._lock:
            for backend in job.backends:
                holders = self._holders.get(backend)
                if holders and job.id in holders:
                    holders.remove(job.id)
                if holders is not None and not holders:
                    del self._holders[backend]
            self._restamp()
        self._wake.set()

    def _settle(self, job: Job, status: str) -> None:
        """Close a job in one of the three terminal states and announce it."""
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

    def _chain(self, job: Job) -> None:
        """Queue whatever follows this job, if anything.

        A convenience and not part of the result: when it fails the job that just finished
        is still finished, and only the next link is lost.
        """
        if self.after_success is None:
            return
        try:
            self.after_success(self, job)
        except Exception as exc:  # noqa: BLE001 - el trabajo ya terminó bien
            logger.warning(f"No se pudo encadenar nada tras «{job.label}»: {exc}")

def uses_subprocess(kind: str) -> bool:
    """Whether this kind of job runs out of process."""
    return kind in SUBPROCESS_KINDS
