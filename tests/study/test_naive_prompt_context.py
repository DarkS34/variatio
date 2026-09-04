"""The two baselines are told what the subject is about, in both prompt sets.

Without the block the commercial and the RAG proposals had to guess the material — the
programming language included — so a session measured that guess instead of the system.
"""

import pytest

from study import prompts as study_prompts

BLOCK = "Curso de primer año de programación en Python. Los enunciados van en castellano."


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_naive_prompt_carries_the_subject_context_whole(language):
    prompt = study_prompts.of(language).naive_generation_prompt(
        subject="Programación",
        educational_level="primer curso",
        language_of_instruction="castellano",
        concepts=["Función"],
        keys=["enunciado"],
        context_block=BLOCK,
    )
    assert BLOCK in prompt
    # The three facts are still spoken by name: the block is added, not substituted.
    assert "Programación" in prompt and "primer curso" in prompt and "castellano" in prompt


@pytest.mark.parametrize("language", ["es", "en"])
def test_an_empty_block_adds_no_section(language):
    render = study_prompts.of(language).naive_generation_prompt
    common = dict(
        subject="Programación",
        educational_level="",
        language_of_instruction="",
        concepts=["Función"],
        keys=["enunciado"],
    )
    assert render(**common) == render(**common, context_block="   ")


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_rag_prompt_inherits_it_through_the_naive_one(language):
    prompts = study_prompts.of(language)
    naive = prompts.naive_generation_prompt(
        subject="Programación",
        educational_level="",
        language_of_instruction="",
        concepts=["Función"],
        keys=["enunciado"],
        context_block=BLOCK,
    )
    rag = prompts.rag_generation_prompt(naive, "", "", "{}")
    assert BLOCK in rag
