"""The transcription job: an accelerator, never a gate.

It fills the markdown cache the three builders read, so a build launched afterwards finds
its pages already written. Nothing waits for it and nothing is chained after it — a build
with a cold cache transcribes on its own exactly as it always did — which is why it is
absent from `JOB_ARTIFACT`, from `SUBPROCESS_KINDS`, from `GATES` and from `CHAINS`.
"""

import pytest

from server.jobs import chain, handlers
from server.jobs.models import JOB_ARTIFACT, JOB_LABELS, SUBPROCESS_KINDS, Job
from server.routers.jobs import GATES, NEEDS_APPROVED
from variatio import stages
from variatio.core.workspace import Workspace


@pytest.fixture
def stub(monkeypatch, tmp_path):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(
        handlers, "_workspace", lambda job: Workspace(tmp_path / job.workspace, slug=job.workspace)
    )

    def transcribe_slot(ws, slot: str) -> dict:
        calls.append((ws.slug, slot))
        return {"slot": slot, "documents": 2, "pages": 7}

    monkeypatch.setattr(stages, "transcribe_slot", transcribe_slot, raising=False)
    return calls


def test_the_job_kind_is_declared_with_a_label():
    assert JOB_LABELS["transcribe"] == "Transcribir los documentos"
    assert "transcribe" in handlers.HANDLERS


def test_it_produces_no_artifact_runs_in_a_thread_and_gates_on_nothing():
    assert "transcribe" not in JOB_ARTIFACT
    assert "transcribe" not in SUBPROCESS_KINDS
    assert "transcribe" not in GATES
    assert "transcribe" not in NEEDS_APPROVED
    assert Job(kind="transcribe").artifact is None


def test_nothing_is_chained_after_transcribing():
    assert "transcribe" not in chain.CHAINS
    for followers in chain.CHAINS.values():
        assert "transcribe" not in followers


@pytest.mark.parametrize("slot", ["corpus", "exemplars"])
def test_the_handler_forwards_the_slot_and_the_workspace(stub, slot):
    job = Job(kind="transcribe", params={"slot": slot}, workspace="aula")

    result = handlers.HANDLERS["transcribe"](job, None)

    assert stub == [("aula", slot)]
    assert result == {"slot": slot, "documents": 2, "pages": 7}


@pytest.mark.parametrize("slot", ["", "raw", None])
def test_an_unknown_slot_is_refused_before_anything_is_read(stub, slot):
    job = Job(kind="transcribe", params={"slot": slot}, workspace="aula")

    with pytest.raises(ValueError, match="Ranura desconocida"):
        handlers.HANDLERS["transcribe"](job, None)
    assert stub == []
