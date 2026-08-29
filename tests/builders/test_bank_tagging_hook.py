import json

import pytest

from variatio.concept_tagger import ConceptTagger
from variatio.core.json_io import write_json
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ExemplarsProfile
from variatio.stages import build

from ..conftest import CHAIN_GRAPH, PROFILE


class _FakeEmbedder:
    def __init__(self):
        self.enriched = []

    def enrich_index_with_content(self, bank):
        self.enriched.append(bank)


@pytest.fixture
def stocked(tmp_path):
    ws = Workspace(root=tmp_path / "aula", slug="aula")
    write_json(ws.kg_path, CHAIN_GRAPH)
    write_json(ws.exemplars_profile_path, PROFILE)
    return ws, ExemplarsProfile(ws.exemplars_profile_path)


def test_the_hook_hands_the_workspace_to_the_tagger(stocked, monkeypatch):
    ws, profile = stocked
    seen = {}

    def fake_embedder(workspace, *args, **kwargs):
        seen["embedder_ws"] = workspace
        return _FakeEmbedder()

    def fake_tag_all(self, bank, ids=None, on_item=None):
        seen["tagger"] = self
        return bank

    monkeypatch.setattr(build, "make_embedder", fake_embedder)
    monkeypatch.setattr(ConceptTagger, "tag_all", fake_tag_all)

    annotate = build._tagging_hook(ws, profile, ws.exemplars_bank_building_path)
    assert annotate is not None

    bank = {"C001": {"enunciado": "Escribe una función recursiva."}}
    assert annotate(bank, ["C001"]) == bank

    assert seen["embedder_ws"] is ws
    assert isinstance(seen["tagger"], ConceptTagger)
    assert seen["tagger"].prompts is not None


def test_the_hook_is_none_without_a_graph(tmp_path):
    ws = Workspace(root=tmp_path / "vacio", slug="vacio")
    write_json(ws.exemplars_profile_path, PROFILE)
    profile = ExemplarsProfile(ws.exemplars_profile_path)

    assert build._tagging_hook(ws, profile, ws.exemplars_bank_building_path) is None


def test_a_cancelled_tagging_keeps_what_was_decided_in_the_working_file(stocked, monkeypatch):
    ws, profile = stocked

    def fake_tag_all(self, bank, ids=None, on_item=None):
        on_item("C001", {"enunciado": "ya etiquetado", "concepts": ["Recursividad"]})
        raise KeyboardInterrupt

    monkeypatch.setattr(build, "make_embedder", lambda *a, **k: _FakeEmbedder())
    monkeypatch.setattr(ConceptTagger, "tag_all", fake_tag_all)

    annotate = build._tagging_hook(ws, profile, ws.exemplars_bank_building_path)
    with pytest.raises(KeyboardInterrupt):
        annotate({"C001": {"enunciado": "sin etiquetar"}}, ["C001"])

    # Into the file the build is writing, never the artifact it has not replaced yet.
    saved = json.loads(ws.exemplars_bank_building_path.read_text(encoding="utf-8"))
    assert saved["C001"]["concepts"] == ["Recursividad"]
    assert not ws.exemplars_bank_path.exists()
