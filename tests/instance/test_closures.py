from variatio.instance.knowledge_graph import KnowledgeGraph

from ..conftest import PREREQUISITE


def graph(path):
    return KnowledgeGraph(str(path))


def test_prerequisite_closure_crosses_more_than_one_hop(chain_graph_path):
    assert graph(chain_graph_path).prerequisite_closure(["Recursividad"], PREREQUISITE) == [
        "Función",
        "Variable",
    ]


def test_dependent_closure_crosses_more_than_one_hop(chain_graph_path):
    assert graph(chain_graph_path).dependent_closure(["Función"], PREREQUISITE) == [
        "Memoización",
        "Recursividad",
    ]


def test_closures_exclude_the_starting_concepts(chain_graph_path):
    found = graph(chain_graph_path).prerequisite_closure(
        ["Recursividad", "Función"], PREREQUISITE
    )
    assert found == ["Variable"]


def test_closure_of_the_deepest_concept_is_empty(chain_graph_path):
    assert graph(chain_graph_path).prerequisite_closure(["Variable"], PREREQUISITE) == []


def test_closure_ignores_a_concept_outside_the_graph(chain_graph_path):
    assert graph(chain_graph_path).prerequisite_closure(["Inexistente"], PREREQUISITE) == []


def test_closure_of_an_unknown_relation_is_empty(chain_graph_path):
    assert graph(chain_graph_path).prerequisite_closure(["Recursividad"], "no existe") == []


def test_closure_of_a_non_directed_relation_is_empty(tmp_path):
    import json

    data = {
        "concepts_by_domains": {"Fundamentos": ["Variable", "Función"]},
        "generic_non_taggable_concepts": [],
        "relations": [
            {
                "details": {
                    "key": "relacionado",
                    "verbose": "se relaciona con",
                    "directed": False,
                    "acyclic": False,
                    "use_in_embedding": True,
                },
                "relations_data": {"Función": ["Variable"]},
            }
        ],
    }
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert graph(path).prerequisite_closure(["Función"], "se relaciona con") == []
