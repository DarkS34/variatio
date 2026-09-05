"""The guardrail screens against the criteria configured now, not at import."""

from variatio.screening import guardrail


def test_the_criteria_are_read_at_call_time(monkeypatch):
    asked = []

    def _record(text, criterion):
        asked.append(criterion)
        return False

    monkeypatch.setattr(guardrail, "_score", _record)
    monkeypatch.setattr(guardrail.config, "GUARDRAIL_CRITERIA", ["harm", "off_topic"])

    guardrail.check("una lista de ejercicios sobre bucles")

    assert asked == ["harm", "off_topic"]


def test_an_explicit_list_still_wins_over_the_configured_one(monkeypatch):
    asked = []

    def _record(text, criterion):
        asked.append(criterion)
        return False

    monkeypatch.setattr(guardrail, "_score", _record)
    monkeypatch.setattr(guardrail.config, "GUARDRAIL_CRITERIA", ["harm"])

    guardrail.check("una lista de ejercicios sobre bucles", criteria=["jailbreak"])

    assert asked == ["jailbreak"]


def test_an_empty_list_is_an_instruction_and_not_an_absence(monkeypatch):
    def _explode(text, criterion):
        raise AssertionError("no debería puntuar ningún criterio")

    monkeypatch.setattr(guardrail, "_score", _explode)
    monkeypatch.setattr(guardrail.config, "GUARDRAIL_CRITERIA", ["harm"])

    verdict = guardrail.check("una lista de ejercicios sobre bucles", criteria=[])

    assert not verdict.blocked
    assert verdict.checked
