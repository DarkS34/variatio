import numpy as np
import pytest

from variant_generator import checks, config
from variant_generator.concept_tagger import TRACE_KEY


class _FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]):
        self.vectors = vectors

    def embed_document(self, text: str):
        return np.array(self.vectors[text], dtype="float32")


class _FakeTagger:
    def __init__(self, primary: str | None):
        self.primary = primary

    def tag(self, text: str) -> dict:
        return {
            "primary_concept": self.primary,
            "concepts": [self.primary] if self.primary else [],
            TRACE_KEY: {"method": "fake"},
        }


@pytest.fixture
def ejercicio(profile):
    return profile.item_type("ejercicio")


def _item(ejercicio, enunciado: str):
    return ejercicio.content_item(enunciado=enunciado, nivel_dificultad="basico")


def _run(ejercicio, item, *, forbidden=(), few_shot=(), vectors=None, tagger=None):
    return checks.run(
        item,
        ejercicio,
        targets=["Recursividad"],
        forbidden=list(forbidden),
        embedder=_FakeEmbedder(vectors or {}),
        tagger=tagger,
        few_shot=list(few_shot),
        batch=[],
    )


def test_a_clean_item_is_accepted(ejercicio):
    item = _item(ejercicio, "Escribe una función recursiva que sume una lista de números.")
    result = _run(ejercicio, item, tagger=_FakeTagger("Recursividad"))
    assert result["verdict"] == "accept"
    assert result["reasons"] == []
    assert result["flags"] == []
    assert not checks.needs_retry(result)


def test_a_forbidden_mention_asks_for_a_retry(ejercicio):
    item = _item(ejercicio, "Aplica memoización para acelerar la función recursiva de Fibonacci.")
    result = _run(ejercicio, item, forbidden=["Memoización"])
    assert result["verdict"] == "retry"
    assert result["forbidden"] == ["Memoización"]
    assert result["reasons"] == ["menciona lo no impartido: Memoización"]
    assert checks.needs_retry(result)
    assert checks.correction_text(result) == "- menciona lo no impartido: Memoización"


def test_a_near_copy_asks_for_a_retry(ejercicio):
    text = "Escribe una función recursiva que calcule el factorial de un número entero."
    twin = "Escribe una función recursiva que calcule el factorial de un entero."
    item = _item(ejercicio, text)
    vectors = {text: [1.0, 0.0], twin: [1.0, 0.0]}
    result = _run(ejercicio, item, few_shot=[("ex1", {"enunciado": twin})], vectors=vectors)
    assert result["similarity"]["high"] is True
    assert result["similarity"]["score"] >= config.CHECK_SIMILARITY_THRESHOLD
    assert result["verdict"] == "retry"
    assert len(result["reasons"]) == 1
    assert result["reasons"][0].startswith("muy parecida a ex1")


def test_an_off_target_tagger_alone_is_a_flag_and_never_a_retry(ejercicio):
    item = _item(ejercicio, "Escribe una función recursiva que invierta una cadena de texto.")
    result = _run(ejercicio, item, tagger=_FakeTagger("Variable"))
    assert result["tagger"]["on_target"] is False
    assert result["flags"] == ["el etiquetador no la reconoce como Recursividad"]
    assert result["reasons"] == []
    assert result["verdict"] == "accept"
    assert not checks.needs_retry(result)


def test_the_flags_keep_every_signal_and_the_reasons_only_the_hard_ones(ejercicio):
    item = _item(ejercicio, "Usa memoización en una función recursiva que invierta una cadena.")
    result = _run(ejercicio, item, forbidden=["Memoización"], tagger=_FakeTagger("Variable"))
    assert len(result["flags"]) == 2
    assert result["reasons"] == ["menciona lo no impartido: Memoización"]
    assert result["verdict"] == "retry"


def test_needs_retry_tolerates_a_missing_result():
    assert not checks.needs_retry(None)
    assert not checks.needs_retry({})
    assert checks.correction_text(None) == ""
