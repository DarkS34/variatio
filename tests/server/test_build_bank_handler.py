"""The two things the parent process does around a bank build, and only around that one.

The bank is the artifact a build replaces in place — it has no draft to land beside — so
this process snapshots it before the worker starts, and removes what the worker was writing
when the build does not finish. Both belong here and not in the builder: a cancel kills the
worker five seconds after asking it to stop, so its own cleanup is the exception.
"""

import json

import pytest

from server import review
from server.jobs import handlers
from variatio.core import progress
from variatio.core.workspace import Workspace

BANK = {"C001": {"enunciado": "El de antes"}}


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "aula", slug="aula")
    workspace.instance_dir.mkdir(parents=True)
    workspace.exemplars_bank_path.write_text(
        json.dumps(BANK, ensure_ascii=False), encoding="utf-8"
    )
    return workspace


@pytest.fixture
def handler(ws, monkeypatch):
    monkeypatch.setattr(handlers, "_workspace", lambda job: ws)
    monkeypatch.setattr(handlers.mirror, "mirror_file", lambda *a, **k: None)
    monkeypatch.setattr(handlers.deps, "invalidate", lambda *a, **k: None)
    return handlers


def _job(kind="build_bank"):
    return handlers.Job(kind=kind, workspace="aula")


def _snapshots(ws, artifact=review.EXEMPLARS_BANK):
    directory = ws.history_dir / artifact
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]


def test_the_bank_is_snapshotted_before_the_build_starts(handler, ws, monkeypatch):
    monkeypatch.setattr(handler, "run_build", lambda artifact, control: {"artifact": artifact})

    handler.HANDLERS["build_bank"](_job(), None)

    assert _snapshots(ws) == [BANK]


def test_a_cancelled_build_takes_its_working_file_with_it(handler, ws, monkeypatch):
    ws.exemplars_bank_building_path.write_text('{"C001": {}}', encoding="utf-8")

    def cancel(artifact, control):
        raise progress.Cancelled("cancelado")

    monkeypatch.setattr(handler, "run_build", cancel)

    with pytest.raises(progress.Cancelled):
        handler.HANDLERS["build_bank"](_job(), None)

    assert not ws.exemplars_bank_building_path.exists()
    assert json.loads(ws.exemplars_bank_path.read_text(encoding="utf-8")) == BANK


def test_the_artifacts_with_a_draft_are_not_snapshotted_here(handler, ws, monkeypatch):
    ws.kg_path.write_text('{"concepts_by_domains": {}}', encoding="utf-8")
    monkeypatch.setattr(handler, "run_build", lambda artifact, control: {"artifact": artifact})

    handler.HANDLERS["build_kg"](_job("build_kg"), None)

    # `retire_curated` is what files the curated graph, and only once a draft exists.
    assert not (ws.history_dir / review.KNOWLEDGE_GRAPH).exists()
