import json

import pytest

from server import approvals
from server.jobs.bus import EventBus
from server.jobs.handlers import HANDLERS
from server.jobs.catalogue import JOB_ARTIFACT, Job
from server.jobs.runner import JobRunner
from server.approvals import Approvals
from variatio.core.workspace import Workspace

BANK = {"C001": {"enunciado": "Suma dos números.", "item_type": "ejercicio"}}


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "aula", slug="aula")
    workspace.artifacts_dir.mkdir(parents=True)
    workspace.exemplars_bank_path.write_text(json.dumps(BANK), encoding="utf-8")
    return workspace


@pytest.fixture
def runner(monkeypatch):
    return JobRunner(EventBus(), HANDLERS)


def test_tagging_puts_the_bank_into_the_building_state(runner, ws):
    runner.submit("tag", {}, workspace="aula")

    building = runner.building_artifacts("aula")
    assert building == {approvals.EXEMPLARS_BANK}
    assert Approvals(ws).state(approvals.EXEMPLARS_BANK, building)["status"] == "building"


def test_tagging_is_filed_under_the_bank_without_being_a_rebuild(runner):
    job = runner.submit("tag", {}, workspace="aula")

    assert job.to_dict()["artifact"] == approvals.EXEMPLARS_BANK
    assert not job.kind.startswith("build_")


def test_only_the_three_builders_write_an_artifact_whole():
    rebuilds = {kind for kind in JOB_ARTIFACT if kind.startswith("build_")}
    assert rebuilds == {"build_profile", "build_kg", "build_bank"}
    assert set(JOB_ARTIFACT) - rebuilds == {"tag"}


def test_a_taggability_review_leaves_the_graph_alone(runner, ws):
    runner.submit("review_taggability", {}, workspace="aula")

    assert runner.building_artifacts("aula") == set()
    assert Job(kind="review_taggability").artifact is None


@pytest.mark.parametrize("closed", [True, False], ids=["closed", "draft"])
def test_retagging_keeps_a_closed_bank_closed_and_a_draft_a_draft(monkeypatch, ws, closed):
    """Tagging is the system's derivation: it seals a closed bank again, never opens one."""
    from types import SimpleNamespace

    from server.jobs import handlers

    if closed:
        Approvals(ws).approve(approvals.EXEMPLARS_BANK)

    def tag_bank(_context, ids=None):
        tagged = {"C001": {**BANK["C001"], "concepts": ["Suma"]}}
        ws.exemplars_bank_path.write_text(json.dumps(tagged), encoding="utf-8")
        return tagged

    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(handlers, "_workspace", lambda _job: ws)
    monkeypatch.setattr(
        handlers, "context_for", lambda _job: SimpleNamespace(exemplars_bank=dict(BANK))
    )
    monkeypatch.setattr(handlers.entrypoints, "tag_bank", tag_bank)

    handlers.handle_tag(Job(kind="tag", params={"all": True}, workspace="aula"), None)

    status = Approvals(ws).state(approvals.EXEMPLARS_BANK)["status"]
    assert status == ("approved" if closed else "draft")
