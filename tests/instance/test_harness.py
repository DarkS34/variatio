from variatio.instance.knowledge_graph import KnowledgeGraph

from ..conftest import PREREQUISITE


def test_chain_graph_loads(chain_graph_path):
    graph = KnowledgeGraph(str(chain_graph_path))
    assert graph.taggable_concepts == [
        "Variable",
        "Función",
        "Recursividad",
        "Memoización",
    ]
    assert graph.has_relation(PREREQUISITE)


def test_chain_is_three_hops_deep(chain_graph_path):
    graph = KnowledgeGraph(str(chain_graph_path))
    assert graph.neighbors("Memoización", PREREQUISITE, direction="out") == ["Recursividad"]
    assert graph.neighbors("Recursividad", PREREQUISITE, direction="out") == ["Función"]
    assert graph.neighbors("Función", PREREQUISITE, direction="out") == ["Variable"]
