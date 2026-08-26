import json

import pytest

from variatio.instance.knowledge_graph import KnowledgeGraph
from variatio.variatio import VariantGenerator

from ..conftest import CHAIN_GRAPH


class _FakeItemType:
    field_specs: dict = {}


def _graph(tmp_path):
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return KnowledgeGraph(str(path))


def _generator(graph: KnowledgeGraph) -> VariantGenerator:
    generator = object.__new__(VariantGenerator)
    generator.knowledge_graph = graph
    generator.taggable_concepts = set(graph.taggable_concepts)
    return generator


def test_an_empty_curriculum_is_no_restriction(tmp_path):
    generator = _generator(_graph(tmp_path))
    generator._validate_input(_FakeItemType(), ["Variable"], {}, 1, [], "")


def test_a_non_empty_curriculum_still_rejects_a_target_outside_it(tmp_path):
    generator = _generator(_graph(tmp_path))
    with pytest.raises(ValueError, match="Target concepts not contained in curriculum"):
        generator._validate_input(_FakeItemType(), ["Función"], {}, 1, ["Variable"], "")


def test_a_curriculum_may_contain_a_non_taggable_concept(tmp_path):
    graph = _graph(tmp_path)
    assert "Notación asintótica" not in graph.taggable_concepts
    assert "Notación asintótica" in graph.all_concepts
    generator = _generator(graph)
    generator._validate_input(
        _FakeItemType(),
        ["Recursividad"],
        {},
        1,
        ["Recursividad", "Notación asintótica"],
        "",
    )


def test_a_curriculum_still_rejects_a_name_absent_from_the_graph(tmp_path):
    generator = _generator(_graph(tmp_path))
    with pytest.raises(ValueError, match="Unknown curriculum concepts"):
        generator._validate_input(
            _FakeItemType(), ["Variable"], {}, 1, ["Variable", "Inexistente"], ""
        )
