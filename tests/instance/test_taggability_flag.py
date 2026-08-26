import json

from variant_generator.instance.knowledge_graph import KnowledgeGraph

from ..conftest import CHAIN_GRAPH


def write(tmp_path, data):
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return KnowledgeGraph(str(path))


def test_a_graph_without_the_flag_reports_the_review_as_pending(chain_graph_path):
    assert KnowledgeGraph(str(chain_graph_path)).taggability_reviewed is False


def test_a_reviewed_graph_reports_it(tmp_path):
    graph = write(tmp_path, CHAIN_GRAPH | {"taggability_reviewed": True})
    assert graph.taggability_reviewed is True


def test_an_explicit_pending_review_leaves_the_exclusion_list_alone(tmp_path):
    graph = write(tmp_path, CHAIN_GRAPH | {"taggability_reviewed": False})
    assert graph.generic_non_taggable_concepts == {"Notación asintótica"}
    assert graph.taggable_concepts == [
        c for c in graph.all_concepts if c != "Notación asintótica"
    ]


def test_a_legacy_graph_keeps_its_exclusions_with_no_flag_at_all(tmp_path):
    assert "taggability_reviewed" not in CHAIN_GRAPH
    graph = write(tmp_path, CHAIN_GRAPH)
    assert graph.taggability_reviewed is False
    assert graph.generic_non_taggable_concepts == {"Notación asintótica"}
    assert len(graph.taggable_concepts) == len(graph.all_concepts) - 1


def test_a_graph_nobody_judged_leaves_every_concept_taggable(tmp_path):
    graph = write(
        tmp_path,
        CHAIN_GRAPH | {"generic_non_taggable_concepts": [], "taggability_reviewed": False},
    )
    assert graph.taggable_concepts == graph.all_concepts
