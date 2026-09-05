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
    workspace.instance_dir.mkdir(parents=True)
    workspace.exemplars_bank_path.write_text(json.dumps(BANK), encoding="utf-8")
    return workspace


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)
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
