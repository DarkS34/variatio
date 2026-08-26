import json

from server import curriculum
from variatio.core.workspace import Workspace
from variatio.instance.knowledge_graph import KnowledgeGraph

from ..conftest import CHAIN_GRAPH


def workspace(tmp_path):
    ws = Workspace(root=tmp_path, slug="test")
    ws.instance_dir.mkdir(parents=True, exist_ok=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return ws, KnowledgeGraph(str(ws.kg_path))


def test_an_undefined_curriculum_reads_as_empty(tmp_path):
    ws, graph = workspace(tmp_path)
    assert curriculum.load(ws, graph) == {"concepts": [], "updated_at": None, "dropped": []}


def test_saving_then_loading_round_trips(tmp_path):
    ws, graph = workspace(tmp_path)
    curriculum.save(ws, ["Variable", "Función"], graph)
    assert curriculum.load(ws, graph)["concepts"] == ["Función", "Variable"]


def test_saving_rejects_a_concept_outside_the_graph(tmp_path):
    ws, graph = workspace(tmp_path)
    curriculum.save(ws, ["Variable", "Inexistente"], graph)
    assert curriculum.load(ws, graph)["concepts"] == ["Variable"]


def test_a_concept_that_left_the_graph_is_reported_not_hidden(tmp_path):
    ws, graph = workspace(tmp_path)
    curriculum.save(ws, ["Variable", "Función"], graph)
    shrunk = dict(CHAIN_GRAPH)
    shrunk["concepts_by_domains"] = {"Fundamentos": ["Variable"]}
    ws.kg_path.write_text(json.dumps(shrunk, ensure_ascii=False), encoding="utf-8")
    state = curriculum.load(ws, KnowledgeGraph(str(ws.kg_path)))
    assert state["concepts"] == ["Variable"]
    assert state["dropped"] == ["Función"]


def test_emptying_a_curriculum_is_a_save_and_not_an_absence(tmp_path):
    ws, graph = workspace(tmp_path)
    curriculum.save(ws, ["Variable", "Función"], graph)
    state = curriculum.save(ws, [], graph)
    assert state["concepts"] == []
    assert state["updated_at"] is not None
    assert curriculum.resolve(ws, graph, None) is None


def test_an_explicit_empty_curriculum_lifts_the_stored_one(tmp_path):
    ws, graph = workspace(tmp_path)
    curriculum.save(ws, ["Variable", "Función"], graph)
    assert curriculum.resolve(ws, graph, []) == []


def test_an_explicit_curriculum_replaces_the_stored_one(tmp_path):
    ws, graph = workspace(tmp_path)
    curriculum.save(ws, ["Función", "Recursividad"], graph)
    assert curriculum.resolve(ws, graph, ["Variable"]) == ["Variable"]


def test_a_non_taggable_concept_can_still_be_covered(tmp_path):
    ws, graph = workspace(tmp_path)
    assert "Notación asintótica" not in graph.taggable_concepts
    assert "Notación asintótica" in graph.all_concepts
    curriculum.save(ws, ["Variable", "Notación asintótica"], graph)
    state = curriculum.load(ws, graph)
    assert state["concepts"] == ["Notación asintótica", "Variable"]
    assert state["dropped"] == []
