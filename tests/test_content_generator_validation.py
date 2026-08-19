import json

import pytest

from variant_generator.content_generator import ContentGenerator
from variant_generator.knowledge_graph import KnowledgeGraph

from .conftest import CHAIN_GRAPH


class _FakeItemType:
    field_specs: dict = {}


def _graph(tmp_path):
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return KnowledgeGraph(str(path))


def _generator(graph: KnowledgeGraph) -> ContentGenerator:
    generator = object.__new__(ContentGenerator)
    generator.taggable_concepts = set(graph.taggable_concepts)
    return generator


def test_an_empty_curriculum_is_no_restriction(tmp_path):
    generator = _generator(_graph(tmp_path))
    generator._validate_input(_FakeItemType(), ["Variable"], {}, 1, [], "")


def test_a_non_empty_curriculum_still_rejects_a_target_outside_it(tmp_path):
    generator = _generator(_graph(tmp_path))
    with pytest.raises(ValueError, match="Target concepts not contained in curriculum"):
        generator._validate_input(_FakeItemType(), ["Función"], {}, 1, ["Variable"], "")
