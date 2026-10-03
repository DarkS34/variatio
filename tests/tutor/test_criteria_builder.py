"""A criterion is kept only when it cites what it was given; subject-wide ones are merged."""

import json

from tutor import criteria_builder
from tutor.passages import Passage

from .conftest import SOURCES

NOTES = [
    Passage("P1", "apuntes.pdf", "Tema 2 Avanzado > Recursividad", "Avanzado",
            "Nunca uses variables globales dentro de una función recursiva.\n\nLa recursividad es elegante."),
    Passage("P2", "apuntes.pdf", "Tema 1 Fundamentos", "Fundamentos", "Una variable guarda un valor."),
]


def unit_answer(**override):
    answer = {
        "criteria": [
            {"text": "No uses globales en una función recursiva.", "strength": "must", "scope": "unit",
             "concepts": ["Recursividad", "Inventado"], "evidence": ["P1"]},
            {"text": "Usa nombres con significado.", "strength": "should", "scope": "subject",
             "concepts": [], "evidence": ["S1"]},
            {"text": "Algo sin cita.", "strength": "must", "scope": "unit", "concepts": [], "evidence": ["P99"]},
        ],
        "forbidden": [{"term": "global", "reason": "Los apuntes lo desaconsejan.", "evidence": ["P1"]}],
    }
    answer.update(override)
    return json.dumps(answer, ensure_ascii=False)


def test_each_unit_keeps_only_what_it_cited_and_maps_citations_to_places(tutor_context, engine):
    tutor_context.exemplars_bank["C001"]["solucion"] = "def factorial(n):\n    return 1 if n == 0 else n * factorial(n - 1)"
    scripted = engine(other=[unit_answer(), json.dumps({"criteria": [], "forbidden": []})])

    drafted = criteria_builder.build_criteria(tutor_context, SOURCES, NOTES)

    fundamentos, avanzado = drafted["units"]["Fundamentos"], drafted["units"]["Avanzado"]
    assert [c["text"] for c in fundamentos] == ["No uses globales en una función recursiva."]
    assert fundamentos[0]["concepts"] == [] or "Inventado" not in fundamentos[0]["concepts"]
    assert avanzado == []
    assert drafted["built"]["dropped"] == 1
    assert [t["term"] for t in drafted["forbidden_terms"]] == ["global"]
    first_prompt = scripted.calls[0]["prompt"]
    assert "Unidad: «Fundamentos»" in first_prompt


def test_a_forbidden_term_is_a_name_as_code_writes_it_and_not_a_practice():
    evidence = [criteria_builder._Evidence("P1", {"document": "a.pdf", "location": "Tema 1"}, "Nunca uses break.")]
    answer = {
        "criteria": [],
        "forbidden": [
            {"term": "break", "reason": "Rompe el flujo.", "evidence": ["P1"]},
            {"term": "Uso de variables globales para comunicar subprogramas", "reason": "Acopla.", "evidence": ["P1"]},
        ],
    }

    _, _, terms, dropped = criteria_builder._verify(answer, evidence, [])

    assert [t["term"] for t in terms] == ["break"] and dropped == 1


def test_the_normative_paragraphs_lead_the_evidence(tutor_context):
    import re

    from tutor import prompts

    pattern = re.compile(prompts.of("es").NORMATIVE_PATTERN)
    evidence = criteria_builder._notes("Avanzado", ["Recursividad"], SOURCES, NOTES, pattern)

    assert evidence[0].text.startswith("Nunca uses variables globales")
    assert evidence[0].id == "P1"
    assert all(e.place["document"] == "apuntes.pdf" for e in evidence)


def test_subject_wide_criteria_saying_the_same_thing_merge_into_the_first(tutor_context, engine):
    tutor_context.exemplars_bank["C001"]["solucion"] = "def f(n): return n"
    wide = [
        {"text": "Usa nombres con significado.", "strength": "should", "scope": "subject",
         "concepts": [], "evidence": ["P1"]},
        {"text": "Los nombres deben decir qué guardan.", "strength": "must", "scope": "subject",
         "concepts": ["Variable"], "evidence": ["P1"]},
    ]
    engine(other=[
        json.dumps({"criteria": wide, "forbidden": []}),
        json.dumps({"criteria": [], "forbidden": []}),
        json.dumps({"groups": [[1, 2]]}),
    ])

    drafted = criteria_builder.build_criteria(tutor_context, SOURCES, NOTES)

    assert len(drafted["general"]) == 1
    merged = drafted["general"][0]
    assert merged["text"] == "Usa nombres con significado."
    assert merged["strength"] == "must"
    assert merged["concepts"] == ["Variable"]


def test_a_merge_answer_is_always_read_as_a_partition():
    assert criteria_builder._groups({"groups": [[1, 2], [2, 3], [9]]}, 4) == [[0, 1], [2], [3]]
    assert criteria_builder._groups(None, 2) == [[0], [1]]
