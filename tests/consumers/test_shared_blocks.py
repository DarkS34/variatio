"""The chat's shared blocks, in one order, and the reply language both functions follow (D-235)."""

import inspect

import pytest

from consumers.chat import prompts as chat_prompts
from consumers.tutor import prompts as tutor_prompts
from consumers.tutor import checks
from server.conversations import prompts as shared

HEADINGS = {"es": ["LA ASIGNATURA", "IDIOMA", "ALCANCE", "FORMATO"], "en": ["THE COURSE", "LANGUAGE", "SCOPE", "FORMAT"]}


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_chat_carries_the_shared_blocks_in_order(language):
    system = chat_prompts.of(language).system_prompt("- subject: X", "Español", False)
    places = [system.index(f"{heading}\n") for heading in HEADINGS[language]]
    assert places == sorted(places)
    assert shared.of(language).scope_block() in system
    assert shared.of(language).language_block("Español") in system


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_tutor_writes_in_the_subjects_language(language):
    tutor = tutor_prompts.of(language)
    assert "Français" in tutor.method(2, language="Français")
    assert ("español" if language == "es" else "English") in tutor.method(2)


def test_the_two_block_sets_have_the_same_names_and_signatures():
    for name in ("system_prompt", "language_block", "scope_block", "format_block"):
        assert inspect.signature(getattr(shared.es, name)) == inspect.signature(getattr(shared.en, name))


def test_the_language_fact_is_read_as_one_of_ours_or_none():
    assert shared.instruction_code("Español (castellano)") == "es"
    assert shared.instruction_code("English") == "en"
    assert shared.instruction_code("inglés") == "en"
    assert shared.instruction_code("Français") is None
    assert shared.instruction_code("") is None


def test_code_is_seen_in_a_fence_an_inline_span_or_a_statement_line():
    assert shared.has_code(["mira:\n```\nx = 1\n```"])
    assert shared.has_code(["¿por qué falla `print(x)`?"])
    assert shared.has_code(["for i in range(3):\n    total += i;"])
    assert not shared.has_code(["¿Qué es la farmacocinética? Explícamelo: no lo entiendo."])


def test_an_everyday_word_is_looked_for_in_the_code_only():
    reply = "While you think about it, what happens to the counter?"
    assert checks.suggested_terms(reply, ["while"], said="", everyday=frozenset({"while"})) == []
    assert checks.suggested_terms("Use `while` here?", ["while"], said="", everyday=frozenset({"while"})) == ["while"]
    assert checks.suggested_terms(reply, ["while"], said="") == ["while"]


def test_a_reply_loses_only_its_first_sentence():
    assert checks.without_opening("¡Correcto! ¿Y qué pasa con n = 0?") == "¿Y qué pasa con n = 0?"
    assert checks.without_opening("Tienes razón.") == ""
