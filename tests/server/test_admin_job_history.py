"""The panel's list of finished jobs: a window over the runner, which the admin may empty."""

from types import SimpleNamespace

from server import singletons
from server.routers import admin_engine


def _job(job_id: str, status: str, finished_at: float | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id, status=status, finished_at=finished_at, to_dict=lambda: {"id": job_id}
    )


def _runner(monkeypatch, jobs: list) -> None:
    monkeypatch.setattr(singletons, "runner", SimpleNamespace(all=lambda limit=50: jobs))
    monkeypatch.setattr(admin_engine, "_history_cleared_at", 0.0)


def test_only_finished_jobs_are_listed_and_the_oldest_fall_off(monkeypatch):
    jobs = [_job("vivo", "running", None), _job("cola", "queued", None)]
    jobs += [_job(f"j{i}", "succeeded", 1_000.0 - i) for i in range(40)]
    _runner(monkeypatch, jobs)
    listed = admin_engine.job_history(limit=30)["jobs"]
    assert [row["id"] for row in listed] == [f"j{i}" for i in range(30)]


def test_clearing_hides_what_had_finished_and_not_what_finishes_after(monkeypatch):
    _runner(monkeypatch, [_job("viejo", "failed", 1_000.0)])
    monkeypatch.setattr(admin_engine.time, "time", lambda: 2_000.0)
    assert admin_engine.clear_job_history() == {"cleared": True}
    assert admin_engine.job_history(limit=30)["jobs"] == []
    _runner_jobs = [_job("nuevo", "succeeded", 2_500.0), _job("viejo", "failed", 1_000.0)]
    monkeypatch.setattr(singletons, "runner", SimpleNamespace(all=lambda limit=50: _runner_jobs))
    assert [row["id"] for row in admin_engine.job_history(limit=30)["jobs"]] == ["nuevo"]
