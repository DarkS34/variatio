import json

import pytest

from variant_generator.evaluation import Commission
from variant_generator.instance.knowledge_graph import KnowledgeGraph
from variant_generator.stages.evaluate import _validate

from .conftest import CHAIN_GRAPH


class _FakeItemType:
    field_specs: dict = {}


class _FakeContext:
    def __init__(self, graph: KnowledgeGraph):
        self.knowledge_graph = graph


def _graph(tmp_path):
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return KnowledgeGraph(str(path))


def test_a_curriculum_may_contain_a_non_taggable_concept(tmp_path):
    graph = _graph(tmp_path)
    assert "Notación asintótica" not in graph.taggable_concepts
    assert "Notación asintótica" in graph.all_concepts
    commission = Commission(
        concepts=["Recursividad"],
        item_type="x",
        curriculum=["Recursividad", "Notación asintótica"],
    )
    _validate(_FakeContext(graph), _FakeItemType(), commission)


def test_a_curriculum_still_rejects_a_name_absent_from_the_graph(tmp_path):
    graph = _graph(tmp_path)
    commission = Commission(
        concepts=["Variable"],
        item_type="x",
        curriculum=["Variable", "Inexistente"],
    )
    with pytest.raises(ValueError, match="Unknown curriculum concepts"):
        _validate(_FakeContext(graph), _FakeItemType(), commission)
