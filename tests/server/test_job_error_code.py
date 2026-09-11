"""A failed job carries the CODE of its cause when the exception declares one.

The screens used to recognise a refused free text by matching the sentence in `error` —
against a catalogue KEY, and in one language — so the block never reached the form and was
drawn as a generic failure. `error_code` is what a screen branches on instead.
"""

import time

import pytest

from server.jobs import EventBus, JobRunner
from variatio.runtime.screening import InstructionsBlocked


def _run(handler):
    runner = JobRunner(EventBus(), {"boom": handler})
    runner.start()
    try:
        job = runner.submit("boom", {}, workspace="aula")
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and job.status != "failed":
            time.sleep(0.01)
        assert job.status == "failed"
        return job
    finally:
        runner.shutdown(timeout=1.0)


@pytest.fixture(autouse=True)
def _no_run_files(monkeypatch):
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)


def test_a_screened_text_marks_the_job_with_its_code():
    def handler(job, control):
        raise InstructionsBlocked("Las instrucciones adicionales no han pasado la revisión")

    job = _run(handler)
    assert job.error_code == "instructions_blocked"
    assert job.error.startswith("InstructionsBlocked: ")
    assert job.to_dict()["error_code"] == "instructions_blocked"


def test_any_other_failure_carries_no_code():
    def handler(job, control):
        raise ValueError("n must be >= 1")

    job = _run(handler)
    assert job.error_code is None
    assert job.to_dict()["error_code"] is None


def test_a_non_string_code_is_not_believed():
    class Odd(RuntimeError):
        code = 7

    def handler(job, control):
        raise Odd("no")

    assert _run(handler).error_code is None
