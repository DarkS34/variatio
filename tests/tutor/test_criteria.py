"""The subject's criteria are read against the graph, and the curated file wins over the draft."""

import json

from tutor import criteria, paths

DEFAULT = "Pregunta a tu docente."


def test_normalize_drops_what_the_graph_no_longer_has_and_says_so(tutor_context):
    document = {
        "general": [
            {"text": "Nombres con significado.", "strength": "must", "concepts": ["Variable", "Bucle"]},
            {"text": "  ", "strength": "must"},
            {"text": "Nombres con significado.", "strength": "should"},
        ],
        "units": {
            "Avanzado": [{"text": "Siempre un caso base.", "strength": "obligatorio"}],
            "Tema que ya no existe": [{"text": "Algo."}],
        },
        "forbidden_terms": ["break", {"term": "BREAK"}, {"term": "exit", "reason": "No está en los apuntes."}],
        "administrative_reply": "",
    }

    clean, warnings = criteria.normalize(document, tutor_context.knowledge_graph, DEFAULT)

    assert clean["general"] == [
        {"text": "Nombres con significado.", "strength": "must", "concepts": ["Variable"], "sources": []}
    ]
    assert clean["units"] == {
        "Avanzado": [{"text": "Siempre un caso base.", "strength": "should", "concepts": [], "sources": []}]
    }
    assert [t["term"] for t in clean["forbidden_terms"]] == ["break", "exit"]
    assert clean["administrative_reply"] == DEFAULT
    assert any("Bucle" in w for w in warnings)
    assert any("Tema que ya no existe" in w for w in warnings)


def test_the_curated_file_wins_over_the_draft_and_none_reads_as_missing(tutor_context):
    ws = tutor_context.workspace
    graph = tutor_context.knowledge_graph
    assert criteria.load(ws, graph, DEFAULT).origin == criteria.MISSING

    ws.instance_dir.mkdir(parents=True)
    paths.criteria_draft_path(ws).write_text(
        json.dumps({"general": [{"text": "Del borrador."}]}), encoding="utf-8"
    )
    assert criteria.load(ws, graph, DEFAULT).origin == criteria.DRAFT

    paths.criteria_path(ws).write_text(
        json.dumps({"general": [{"text": "Del docente."}]}), encoding="utf-8"
    )
    loaded = criteria.load(ws, graph, DEFAULT)
    assert loaded.origin == criteria.CURATED
    assert [c.text for c in loaded.general] == ["Del docente."]


def test_a_turn_carries_the_general_rules_then_the_focus_s_within_the_budget():
    loaded = criteria.Criteria(
        general=(criteria.Criterion("General."),),
        units={
            "Avanzado": (
                criteria.Criterion("Aviso de la unidad.", "should"),
                criteria.Criterion("Sobre la recursividad.", "should", ("Recursividad",)),
                criteria.Criterion("Obligación de la unidad.", "must"),
            ),
            "Fundamentos": (
                criteria.Criterion("De otra unidad, sobre la recursividad.", "must", ("Recursividad",)),
                criteria.Criterion("De otra unidad, sin relación.", "must"),
            ),
        },
    )

    picked = loaded.for_focus("Avanzado", ["Recursividad"], max_chars=10_000)

    assert [c.text for c in picked] == [
        "General.",
        "Sobre la recursividad.",
        "Obligación de la unidad.",
        "Aviso de la unidad.",
        "De otra unidad, sobre la recursividad.",
    ]
    assert [c.text for c in loaded.for_focus("Avanzado", [], max_chars=20)] == ["General."]


def test_a_term_with_no_letter_is_an_operator_and_is_dropped(tutor_context):
    clean, _ = criteria.normalize(
        {"forbidden_terms": [{"term": "*"}, {"term": "/"}, {"term": "print()"}, {"term": "global"}]},
        tutor_context.knowledge_graph,
        "Pregunta a tu docente.",
    )

    assert [t["term"] for t in clean["forbidden_terms"]] == ["print()", "global"]
