import json

import pytest

from variatio.instance.knowledge_graph import KnowledgeGraph
from variatio.instance.relations import RELATION_SCHEMA_ES

# The domains are deliberately NOT in size order, NOT alphabetical and NOT in the order
# the concepts sort in: any test that passes by accident here proves nothing.
GRAPH = {
    "concepts_by_domains": {
        "Zeta primero": ["Uno", "Dos", "Tres"],
        "Alfa segundo": ["Cuatro"],
        "Media tercero": ["Cinco", "Seis"],
        "Vacío cuarto": [],
    },
    "generic_non_taggable_concepts": [],
    "relations": [],
}


@pytest.fixture
def graph_path(tmp_path):
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(GRAPH, ensure_ascii=False), encoding="utf-8")
    return path


def test_the_loader_states_the_syllabus_order(graph_path):
    kg = KnowledgeGraph(str(graph_path))
    assert kg.domains == ["Zeta primero", "Alfa segundo", "Media tercero", "Vacío cuarto"]
    assert kg.domain_index["Media tercero"] == 2


def test_all_concepts_walks_the_domains_in_that_order(graph_path):
    kg = KnowledgeGraph(str(graph_path))
    assert kg.all_concepts == ["Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis"]
    first_seen = []
    for name in kg.all_concepts:
        domain = kg.concept_domain[name]
        if domain not in first_seen:
            first_seen.append(domain)
    assert first_seen == ["Zeta primero", "Alfa segundo", "Media tercero"]
