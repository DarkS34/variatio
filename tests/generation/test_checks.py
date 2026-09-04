import numpy as np

from variatio import checks
from variatio.instance.exemplars_profile import ItemType
from variatio.variatio import parse_item

PROFILE = {
    "primary_field": "enunciado",
    "fields": {
        "enunciado": {"schema": {"type": "string"}},
        "solucion": {"schema": {"type": ["string", "null"]}},
        "nivel": {"schema": {"type": "string", "enum": ["basico", "avanzado"]}},
    },
}

STATEMENT = "Escribe una función que devuelva la posición del primer impar de una lista."


def _item_type() -> ItemType:
    return ItemType("escritura", PROFILE)


def _item(**overrides):
    data = {"enunciado": STATEMENT, "solucion": "def f(xs): ...", "nivel": "basico", **overrides}
    return _item_type().content_item(**data)


def test_floor_rejects_an_empty_primary_field():
    assert checks.content_floor(_item(enunciado=""), _item_type()) is not None


def test_floor_rejects_a_primary_field_that_is_too_short():
    assert checks.content_floor(_item(enunciado="Suma."), _item_type()) is not None


def test_floor_tolerates_a_nullable_required_field():
    assert checks.content_floor(_item(solucion=None), _item_type()) is None


def test_parse_item_applies_the_floor():
    response = '{"enunciado": "", "solucion": "x", "nivel": "basico"}'
    item, error = parse_item(response, {}, _item_type())
    assert item is None
    assert "enunciado" in error


def test_parse_item_overwrites_an_ignored_fixed_value():
    response = f'{{"enunciado": "{STATEMENT}", "solucion": "x", "nivel": "avanzado"}}'
    item, _ = parse_item(response, {"nivel": "basico"}, _item_type())
    assert item.nivel == "basico"


def test_forbidden_mentions_reads_every_text_field():
    item = _item(solucion="def f(xs):\n    return f(xs[1:])  # recursividad")
    assert checks.forbidden_mentions(item.model_dump(mode="json"), ["Recursividad", "Bucle for"]) == [
        "Recursividad"
    ]


def test_forbidden_mentions_matches_a_short_keyword_literally():
    item = _item(solucion="if x > 0:\n    pass")
    assert checks.forbidden_mentions(item.model_dump(mode="json"), ["if"]) == ["if"]


class _StubEmbedder:
    vectors = {
        "a": np.array([1.0, 0.0]),
        "b": np.array([0.0, 1.0]),
        "c": np.array([0.8, 0.6]),
    }

    def embed_document(self, text: str) -> np.ndarray:
        return self.vectors[text]


def test_nearest_returns_the_closest_label_and_its_score():
    label, score = checks.nearest(_StubEmbedder(), "a", [("B", "b"), ("C", "c")])
    assert label == "C"
    assert score == 0.8


def test_nearest_is_none_without_anything_to_compare():
    assert checks.nearest(_StubEmbedder(), "a", []) is None


class _StubTagger:
    def __init__(self, primary, concepts):
        self._primary, self._concepts = primary, concepts

    def tag(self, text):
        return {"primary_concept": self._primary, "concepts": self._concepts}


def test_roundtrip_is_on_target_when_the_tagger_picks_a_target():
    result = checks.tagger_roundtrip(_StubTagger("Lista", ["Lista", "Bucle"]), STATEMENT, ["Lista"])
    assert result["on_target"] is True
    assert result["targets_found"] == ["Lista"]


def test_roundtrip_is_off_target_when_the_tagger_rejects_everything():
    result = checks.tagger_roundtrip(_StubTagger(None, []), STATEMENT, ["Lista"])
    assert result["on_target"] is False
    assert result["targets_found"] == []


class _TextEmbedder:
    """Every text lands on the same unit vector: similarity is not what these tests ask."""

    def embed_document(self, text: str) -> np.ndarray:
        return np.array([1.0, 0.0])


def _run(rule: str, primary: str, statement: str = STATEMENT) -> dict:
    return checks.run(
        _item(enunciado=statement),
        _item_type(),
        targets=["Lista"],
        forbidden=["Recursividad", "Bucle for"],
        rule=rule,
        embedder=_TextEmbedder(),
        tagger=_StubTagger(primary, [primary, "Lista"]),
        few_shot=[],
        batch=[],
    )


def test_the_rule_follows_the_curriculum():
    assert checks.closure_rule(["Lista"]) == checks.RULE_MENTIONS
    assert checks.closure_rule([]) == checks.RULE_PRACTISES
    assert checks.closure_rule(None) == checks.RULE_PRACTISES


def test_with_a_curriculum_a_mention_of_a_forbidden_concept_is_a_reason():
    verdict = _run(checks.RULE_MENTIONS, "Lista", "Recorre la lista con un bucle for.")
    assert verdict["forbidden"] == ["Bucle for"]
    assert verdict["practised_later"] == []
    assert verdict["verdict"] == "retry"
    assert verdict["reasons"] == ["menciona lo no impartido: Bucle for"]


def test_without_a_curriculum_a_mention_holds_nothing_against_the_item():
    """Practicar ≠ usar: nobody said the loop is untaught, so using it is scaffolding."""
    verdict = _run(checks.RULE_PRACTISES, "Lista", "Recorre la lista con un bucle for.")
    assert verdict["rule"] == checks.RULE_PRACTISES
    assert verdict["forbidden"] == []
    assert verdict["verdict"] == "accept"
    assert verdict["flags"] == []


def test_without_a_curriculum_practising_a_later_concept_is_a_reason():
    verdict = _run(checks.RULE_PRACTISES, "Recursividad")
    assert verdict["practised_later"] == ["Recursividad"]
    assert verdict["verdict"] == "retry"
    assert verdict["reasons"] == ["practica lo que va después del objetivo: Recursividad"]


def test_practising_the_target_itself_is_never_later():
    assert checks.practised_later("Lista", ["Recursividad"]) == []
    assert checks.practised_later(None, ["Recursividad"]) == []
