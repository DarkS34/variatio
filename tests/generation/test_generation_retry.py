from variatio.prompts.es import generate_content_prompt
from variatio.runtime.generator import GeneratedVariant, generate_with_retries


def _prompt(correction=None) -> str:
    return generate_content_prompt(
        context_block="",
        item_type_block="- **Ejercicio** (`ejercicio`)",
        target_concepts_block="- **Recursividad**",
        prerequisites_block="",
        excluded_concepts_block="",
        curriculum_block="",
        rules_block="- Una regla.",
        few_shot_block="",
        already_generated=[],
        instance_template="{}",
        fields_block="- `enunciado` (string)",
        fixed_values_block="",
        correction=correction,
    )


def test_the_correction_section_is_absent_without_a_correction():
    assert "# CORRECCIÓN DE UN INTENTO ANTERIOR" not in _prompt()
    assert "# CORRECCIÓN DE UN INTENTO ANTERIOR" not in _prompt("   ")


def test_the_correction_section_sits_right_before_the_examples():
    prompt = _prompt("- menciona lo no impartido: Memoización")
    heading = prompt.index("# CORRECCIÓN DE UN INTENTO ANTERIOR")
    examples = prompt.index("# EJEMPLOS DE REFERENCIA")
    assert heading < examples
    body = prompt[heading:examples]
    assert "menciona lo no impartido: Memoización" in body
    assert "fue rechazada" in body
    assert "Todo lo demás del encargo se mantiene igual" in body


class _Item:
    def __init__(self, text: str):
        self.enunciado = text

    def model_dump(self, mode="json"):
        return {"enunciado": self.enunciado}


def _variant(text: str) -> GeneratedVariant:
    return GeneratedVariant.model_construct(item=_Item(text), item_type="ejercicio")


def _verdict(retry: bool) -> dict:
    reasons = ["menciona lo no impartido: Memoización"] if retry else []
    return {"reasons": reasons, "flags": list(reasons), "verdict": "retry" if retry else "accept"}


def test_a_clean_item_spends_no_retry():
    calls = []

    def attempt(correction):
        calls.append(correction)
        return _variant("uno")

    result = generate_with_retries(attempt, lambda r: _verdict(False), max_retries=3)
    assert result.retried == 0
    assert calls == [None]


def test_a_retry_carries_the_reasons_and_stops_when_the_verdict_is_accept():
    calls = []
    verdicts = iter([True, False])

    def attempt(correction):
        calls.append(correction)
        return _variant(f"intento {len(calls)}")

    result = generate_with_retries(attempt, lambda r: _verdict(next(verdicts)), max_retries=3)
    assert result.retried == 1
    assert result.item.enunciado == "intento 2"
    assert calls == [None, "- menciona lo no impartido: Memoización"]
    assert result.checks["verdict"] == "accept"


def test_the_budget_caps_the_retries_and_the_last_attempt_is_kept_with_its_flags():
    calls = []

    def attempt(correction):
        calls.append(correction)
        return _variant(f"intento {len(calls)}")

    result = generate_with_retries(attempt, lambda r: _verdict(True), max_retries=2)
    assert len(calls) == 3
    assert result.retried == 2
    assert result.item.enunciado == "intento 3"
    assert result.checks["verdict"] == "retry"


def test_a_zero_budget_makes_the_checks_diagnostic_only():
    calls = []

    def attempt(correction):
        calls.append(correction)
        return _variant("uno")

    result = generate_with_retries(attempt, lambda r: _verdict(True), max_retries=0)
    assert calls == [None]
    assert result.retried == 0
    assert result.checks["verdict"] == "retry"


def test_a_retry_that_fails_to_parse_keeps_the_previous_item():
    calls = []

    def attempt(correction):
        calls.append(correction)
        return _variant("uno") if correction is None else None

    result = generate_with_retries(attempt, lambda r: _verdict(True), max_retries=3)
    assert len(calls) == 2
    assert result is not None
    assert result.item.enunciado == "uno"
    assert result.retried == 0


def test_without_verification_the_first_parse_is_the_answer():
    calls = []

    def attempt(correction):
        calls.append(correction)
        return _variant("uno")

    result = generate_with_retries(attempt, None, max_retries=3)
    assert calls == [None]
    assert result.checks is None


def test_an_unparseable_first_attempt_discards_the_variant():
    assert generate_with_retries(lambda c: None, lambda r: _verdict(False), max_retries=3) is None
