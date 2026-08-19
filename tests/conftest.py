import json

import pytest

CHAIN_GRAPH = {
    "concepts_by_domains": {
        "Fundamentos": ["Variable", "Función"],
        "Avanzado": ["Recursividad", "Memoización"],
    },
    "generic_non_taggable_concepts": [],
    "relations": [
        {
            "details": {
                "key": "prerrequisito",
                "verbose": "tiene como prerrequisito",
                "directed": True,
                "acyclic": True,
                "use_in_embedding": True,
            },
            "relations_data": {
                "Función": ["Variable"],
                "Recursividad": ["Función"],
                "Memoización": ["Recursividad"],
            },
        }
    ],
}

PREREQUISITE = "tiene como prerrequisito"


@pytest.fixture
def chain_graph_path(tmp_path):
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return path
