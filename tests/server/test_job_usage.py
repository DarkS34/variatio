"""What a job's model calls cost is kept in its result and in the subject's usage file."""

import time

from server.jobs import usage_log
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from variatio.core import progress, usage


def _run(handler, monkeypatch):
    monkeypatch.setattr(progress, "current_activity", lambda: "tutor_reply")
    runner = JobRunner(EventBus(), {"pensar": handler})
    runner.start()
    job = runner.submit("pensar", {}, workspace="aula")
    deadline = time.monotonic() + 3
    while job.status not in ("succeeded", "failed", "cancelled") and time.monotonic() < deadline:
        time.sleep(0.02)
    return job


def test_a_job_keeps_what_its_calls_cost(monkeypatch):
    def handler(job, control):
        usage.record("ollama", "qwen", 120, 30)
        usage.record("ollama", "qwen", 80, 10)
        return {"conversation": "c1", "turn": 1}

    job = _run(handler, monkeypatch)

    assert job.status == "succeeded"
    assert job.result["conversation"] == "c1"
    assert job.result["usage"]["calls"] == 2 and job.result["usage"]["in"] == 200
    kept = usage_log.read("aula")
    assert kept[-1]["kind"] == "pensar" and kept[-1]["status"] == "succeeded" and kept[-1]["out"] == 40


def test_a_failed_job_s_cost_is_kept_too_and_a_job_with_no_call_keeps_nothing(monkeypatch):
    before = len(usage_log.read("aula"))

    def failing(job, control):
        usage.record("cerebras", "llama", 10, 0)
        raise RuntimeError("se cortó")

    failed = _run(failing, monkeypatch)
    quiet = _run(lambda job, control: {"ok": True}, monkeypatch)

    assert failed.status == "failed"
    assert quiet.result == {"ok": True}, "no call, no usage"
    kept = usage_log.read("aula")[before:]
    assert [row["status"] for row in kept] == ["failed"]


def test_the_command_sums_a_subject_s_jobs_by_kind(capsys):
    from types import SimpleNamespace

    from server.cli.usage import show_usage

    phases = [{"phase": "tutor_reply", "engine": "ollama", "model": "q", "calls": 1, "in": 900, "out": 100}]
    for _ in range(2):
        usage_log.append("caro", "tutor_turn", "succeeded", {"calls": 1, "in": 900, "out": 100, "phases": phases}, time.time())

    assert show_usage(SimpleNamespace(workspace="caro", days=None)) == 0

    out = capsys.readouterr().out
    line = next(row for row in out.splitlines() if row.startswith("tutor_turn"))
    assert line.split()[1:] == ["2", "2", "1800", "200", "900", "100"]
    assert "ollama" in out
