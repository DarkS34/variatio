"""A concept map is read off the graph, capped, and shown at two moments and no others."""

import json
from types import SimpleNamespace

import numpy as np

from tutor import ATTEMPT, SOCIAL, SOLUTION, THEORY, concept_map
from tutor.card import Card, FocusConcept, Prerequisite, Quote
from variatio.loaders.knowledge_graph import KnowledgeGraph

PREREQUISITE = "tiene como prerrequisito"
PART_OF = "se engloba en"
RELATED = "se relaciona con"

GRAPH = {
    "concepts_by_domains": {
        "Modularidad": ["Subprograma", "Función", "Algoritmia"],
        "Recursividad": [
            "Recursividad", "Caso base", "Subproblema", "Fibonacci", "Sierpinski", "Hanoi",
            "Factorial", "Palíndromo", "Pila", "Autosimilitud", "Isla",
        ],
    },
    "relations": [
        {
            "details": {"verbose": PREREQUISITE, "directed": True, "acyclic": True},
            "relations_data": {
                "Recursividad": ["Función", "Algoritmia"],
                "Función": ["Subprograma"],
                "Subproblema": ["Recursividad"],
                "Fibonacci": ["Recursividad"],
                "Sierpinski": ["Recursividad"],
                "Hanoi": ["Recursividad"],
            },
        },
        {
            "details": {"verbose": PART_OF, "directed": True},
            "relations_data": {"Caso base": ["Recursividad"], "Subproblema": ["Recursividad"]},
        },
        {
            "details": {"verbose": RELATED, "directed": False},
            "relations_data": {"Recursividad": ["Factorial", "Palíndromo", "Pila", "Autosimilitud", "Fibonacci"]},
        },
    ],
}

# How close each concept's description is to «Recursividad»'s: the order a cap keeps them in.
CLOSENESS = {
    "Función": 0.9, "Algoritmia": 0.2,
    "Fibonacci": 0.8, "Subproblema": 0.7, "Hanoi": 0.6, "Sierpinski": 0.1,
    "Caso base": 0.95, "Factorial": 0.85, "Pila": 0.5, "Palíndromo": 0.4, "Autosimilitud": 0.3,
}


def context(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(GRAPH, ensure_ascii=False), encoding="utf-8")
    index = {"Recursividad": np.array([1.0, 0.0])}
    index.update({name: np.array([score, 0.0]) for name, score in CLOSENESS.items()})
    return SimpleNamespace(
        knowledge_graph=KnowledgeGraph(path),
        generator=SimpleNamespace(prerequisite_relation=PREREQUISITE),
        embedder=SimpleNamespace(concepts_index=index),
    )


def test_a_map_is_one_hop_of_the_graph_capped_and_ordered_by_closeness(tmp_path):
    found = concept_map.build("Recursividad", context(tmp_path))

    assert found.unit == "Recursividad"
    assert found.before == ("Función", "Algoritmia")
    assert found.after == ("Fibonacci", "Subproblema", "Hanoi"), "the closest three of four"
    assert [(link.name, link.relation, link.direction) for link in found.links] == [
        ("Caso base", PART_OF, concept_map.IN),
        ("Factorial", RELATED, concept_map.BOTH),
        ("Pila", RELATED, concept_map.BOTH),
    ]
    assert found.hidden == (0, 1, 2), "what does not fit is counted"
    names = [*found.before, *found.after, *(link.name for link in found.links)]
    assert len(names) == len(set(names)), "a concept tied twice is drawn once, as a prerequisite edge first"
    assert found.record()["hidden"] == {"before": 0, "after": 1, "links": 2}


def test_a_concept_the_graph_places_in_no_order_has_no_map(tmp_path):
    assert concept_map.build("Isla", context(tmp_path)) is None
    assert concept_map.build("No existe", context(tmp_path)) is None
    assert concept_map.build("Factorial", context(tmp_path)) is None, "tied, but neither before nor after anything"


def test_the_opening_map_comes_once_per_concept_and_only_with_a_reply_that_works_on_it(tmp_path):
    ctx = context(tmp_path)

    assert concept_map.opening(THEORY, ["Recursividad"], [], ctx).concept == "Recursividad"
    assert concept_map.opening(ATTEMPT, ["Isla", "Función"], [], ctx).concept == "Función"
    assert concept_map.opening(THEORY, ["Recursividad"], ["Recursividad"], ctx) is None
    assert concept_map.opening(SOCIAL, ["Recursividad"], [], ctx) is None
    assert concept_map.opening(SOLUTION, ["Recursividad"], [], ctx) is None


def test_the_review_map_marks_the_prerequisite_once_and_never_right_after_another_map(tmp_path):
    ctx = context(tmp_path)
    sent = ("Recursividad", "Algoritmia")

    found = concept_map.review(THEORY, sent, {"mapped": ["Recursividad"], "since_map": 2}, ctx)
    assert found.review == "Algoritmia" and found.before[0] == "Algoritmia"

    assert concept_map.review(THEORY, sent, {"mapped": ["Recursividad"], "since_map": 1}, ctx) is None
    shown = {"mapped": [concept_map.review_key(*sent)], "since_map": 5}
    assert concept_map.review(THEORY, sent, shown, ctx) is None
    assert concept_map.review(THEORY, None, {"since_map": 5}, ctx) is None
    assert concept_map.review(SOLUTION, sent, {"since_map": 5}, ctx) is None


def a_card() -> Card:
    return Card(
        kind=THEORY,
        focus=(
            FocusConcept(
                name="Recursividad",
                unit="Avanzado",
                anchors=(Quote("apuntes.pdf", "Tema 2 Avanzado > Recursividad", "Se llama a sí misma."),),
                prerequisites=(
                    Prerequisite("Función"),
                    Prerequisite("Iteración"),
                ),
            ),
        ),
    )


def test_a_reply_sends_the_student_back_only_when_one_sentence_names_the_prerequisite_to_review():
    from tutor.prompts import es

    card = a_card()

    def sent(reply):
        return card.sent_back(reply, es.REVIEW_PATTERN)

    assert sent("Si te falta qué es una función, repásalo en los apuntes. ¿Qué hace tu caso base?") == (
        "Recursividad",
        "Función",
    )
    assert sent("Una función recursiva se llama a sí misma. ¿Cuándo para?") is None
    assert sent("Repasa los apuntes con calma. ¿Qué ves?") is None
    apart = sent("Repasa tu respuesta. ¿En qué se parece a una función cualquiera?")
    assert apart is None, "the prerequisite and the review have to share a sentence"
    assert sent("Revisa tu función: ¿qué devuelve cuando n vale 0?") is None, "«revisa» is said of code"
