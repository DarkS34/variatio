"""Asking a job to stop answers at once, however long the job takes to hear it.

`request_cancel` runs on the thread serving `DELETE /api/jobs/{id}`. It used to terminate
the build subprocess and then WAIT five seconds for it — and always the whole five, because
the worker's SIGTERM handler only raises its own cancel flag and leaves at its next
checkpoint. Those five seconds were spent inside the request, so the screen could not even
say the stop had been heard until they were over.

The escalation itself is not optional and is pinned here too: a child that ignores SIGTERM
is killed, or a build with a model call in flight would hold the GPU until it finished.
"""

import subprocess
import sys
import time

import pytest

from server.jobs.bus import EventBus
from server.jobs.models import Job
from server.jobs import runner as runner_module
from server.jobs.runner import JobControl

# A child that ignores SIGTERM, which is what the build worker effectively is: its handler
# only raises a flag, so it leaves at its next checkpoint or not at all.
DEAF = [
    sys.executable,
    "-u",
    "-c",
    "import signal, sys, time\n"
    "signal.signal(signal.SIGTERM, lambda *a: None)\n"
    "print('listo', flush=True)\n"
    "time.sleep(120)\n",
]


@pytest.fixture(autouse=True)
def brief_grace(monkeypatch):
    """Shorten the five-second grace period; what is under test is where it is SPENT."""
    monkeypatch.setattr(runner_module, "_TERMINATE_GRACE_SECONDS", 0.5)


def _control() -> JobControl:
    return JobControl(EventBus(), Job(kind="build_kg", params={}, workspace="w"))


def _deaf() -> subprocess.Popen:
    """Spawn the deaf child and wait until its handler is actually installed.

    Without the wait the test races the interpreter's start-up: a SIGTERM arriving before
    `signal.signal` runs is handled by the DEFAULT handler, the child dies instantly, and
    every assertion here passes against code that blocks for five seconds.
    """
    process = subprocess.Popen(DEAF, stdout=subprocess.PIPE, text=True)
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "listo"
    return process


def test_cancelling_a_deaf_child_returns_immediately():
    control = _control()
    process = _deaf()
    try:
        control.attach_process(process)
        started = time.monotonic()
        control.request_cancel()
        elapsed = time.monotonic() - started
        assert elapsed < 0.2, f"la petición se quedó {elapsed:.1f} s dentro de request_cancel"
        assert control.should_cancel()
    finally:
        process.kill()
        process.wait(timeout=10)


def test_a_child_that_ignores_the_terminate_is_killed_anyway():
    control = _control()
    process = _deaf()
    try:
        control.attach_process(process)
        control.request_cancel()
        # The grace period plus room for a loaded box; without the escalation this child
        # sits there for two minutes.
        assert process.wait(timeout=20) is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def test_a_child_that_leaves_on_its_own_is_not_killed():
    """The grace period is real: a worker that exits cleanly keeps its own exit code."""
    control = _control()
    process = subprocess.Popen([sys.executable, "-c", "raise SystemExit(2)"])
    process.wait(timeout=10)
    control.attach_process(process)
    control.request_cancel()
    assert process.returncode == 2


def test_a_job_with_no_subprocess_only_raises_the_flag():
    control = _control()
    control.request_cancel()
    assert control.should_cancel()


def test_a_cancel_that_arrives_before_the_process_still_reaches_it():
    """`attach_process` kills on adoption when the stop came first — and does not block."""
    control = _control()
    control.request_cancel()
    process = _deaf()
    try:
        started = time.monotonic()
        control.attach_process(process)
        assert time.monotonic() - started < 0.2
        assert process.wait(timeout=20) is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
