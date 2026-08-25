import json

import pytest

from variant_generator.instance.knowledge_graph import KnowledgeGraph

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


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from server.db import mirror
    from variant_generator.core.workspace import Workspace

    monkeypatch.setattr(mirror, "mirror_file", lambda ws, path: None)
    workspace = Workspace(tmp_path, "aula")
    workspace.instance_dir.mkdir(parents=True)
    workspace.kg_path.write_text(json.dumps(GRAPH, ensure_ascii=False), encoding="utf-8")
    return workspace


def order(ws) -> list[str]:
    from server.editors import kg_edit

    return list(kg_edit.raw(ws)["concepts_by_domains"])


def test_reorder_add_rename_and_delete_all_respect_the_order(ws):
    from server.editors import kg_edit

    kg_edit.reorder_domains(ws, ["Alfa segundo", "Vacío cuarto", "Zeta primero", "Media tercero"])
    assert order(ws) == ["Alfa segundo", "Vacío cuarto", "Zeta primero", "Media tercero"]

    kg_edit.add_domain(ws, "Nuevo", after="Vacío cuarto")
    assert order(ws) == [
        "Alfa segundo", "Vacío cuarto", "Nuevo", "Zeta primero", "Media tercero"
    ]

    kg_edit.add_domain(ws, "Al final")
    assert order(ws)[-1] == "Al final"

    kg_edit.rename_domain(ws, "Vacío cuarto", "Renombrado")
    assert order(ws)[1] == "Renombrado"

    kg_edit.delete_domain(ws, "Nuevo")
    assert order(ws) == [
        "Alfa segundo", "Renombrado", "Zeta primero", "Media tercero", "Al final"
    ]


def test_reorder_domains_refuses_anything_that_is_not_an_exact_permutation(ws):
    from server.editors import kg_edit
    from server.editors.kg_edit import KGError

    for bad in (
        ["Zeta primero", "Alfa segundo"],
        ["Zeta primero", "Alfa segundo", "Media tercero", "Vacío cuarto", "Inventado"],
        ["Zeta primero", "Zeta primero", "Alfa segundo", "Media tercero"],
    ):
        with pytest.raises(KGError):
            kg_edit.reorder_domains(ws, bad)
        assert order(ws) == [
            "Zeta primero", "Alfa segundo", "Media tercero", "Vacío cuarto"
        ]
