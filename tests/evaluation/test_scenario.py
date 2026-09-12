"""One scenario per session, shared by both arms: drawn once, unless the instructions fix one.

What is pinned: both prompt sets carry the sentence to the baselines and to the system's
prompt, and both show the draw the evaluator's free text; a draw answers the set's
`SCENARIO_NONE` when that text already fixes a theme and the session then carries none; an
empty draw lands once on the commission the arms receive; a draw the engine refuses leaves
it empty rather than failing the session; and the sentence round-trips through the stored
trace and the CSV.
"""

import pytest

from evaluation import Commission, EvaluationSession
from evaluation import prompts as evaluation_prompts
from evaluation import run as evaluation_run
from evaluation.api import store as evaluation_store
from variatio import prompts
from variatio.core import inference, languages


# THE PROMPTS -----------------------------------------------------------------------------


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_the_baselines_carry_the_scenario_in_both_sets(code):
    module = evaluation_prompts.of(code)
    text = module.naive_generation_prompt("Programación", "primer curso", "castellano", ["Bucles"], ["enunciado"], scenario="Una biblioteca presta libros")
    assert "Una biblioteca presta libros" in text
    bare = module.naive_generation_prompt("Programación", "primer curso", "castellano", ["Bucles"], ["enunciado"])
    assert "biblioteca" not in bare
    draw = module.scenario_prompt("Programación", ["Bucles"], context_block="Curso de Python")
    assert "Bucles" in draw and "Curso de Python" in draw
    assert module.SCENARIO_NONE not in draw
    told = module.scenario_prompt("Programación", ["Bucles"], instructions="Que vaya de una panadería")
    assert "Que vaya de una panadería" in told and module.SCENARIO_NONE in told


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_the_system_prompt_carries_the_scenario_as_its_own_section(code):
    module = prompts.of(code)
    blank = dict(
        context_block="", item_type_block="", target_concepts_block="", prerequisites_block="",
        excluded_concepts_block="", curriculum_block="", rules_block="", few_shot_block="",
        already_generated=[], instance_template="", fields_block="", fixed_values_block="",
    )
    with_scenario = module.generate_content_prompt(**blank, scenario="Una clínica veterinaria")
    without = module.generate_content_prompt(**blank)
    assert "Una clínica veterinaria" in with_scenario
    assert with_scenario.count("\n# ") == without.count("\n# ") + 1


# HOW IT IS SETTLED -----------------------------------------------------------------------


class _Context:
    language = "es"
    prompts = prompts.of("es")

    class content_context:
        subject = "Programación"

        @staticmethod
        def prompt_block():
            return "Curso de Python"


def _commission(instructions: str = "") -> Commission:
    return Commission(concepts=["Bucles"], item_type="ejercicio", model="el-rapido", instructions=instructions)


@pytest.mark.parametrize("answer", ["NINGUNO", "ninguno.", "«Ninguno»\n"])
def test_instructions_that_fix_a_theme_leave_the_scenario_empty(monkeypatch, answer):
    calls: list[dict] = []

    class _Answer:
        response = answer

    def fake_generate(**kw):
        calls.append(kw)
        return _Answer()

    monkeypatch.setattr(inference, "generate", fake_generate)
    assert evaluation_run._settle_scenario(_Context(), _commission("Que vaya de una panadería")) == ""
    assert len(calls) == 1
    assert "Que vaya de una panadería" in calls[0]["prompt"]


def test_an_empty_scenario_is_drawn_once(monkeypatch):
    calls: list[dict] = []

    class _Answer:
        response = '"Una clínica veterinaria gestiona citas y vacunas."\nOtra línea que sobra'

    def fake_generate(**kw):
        calls.append(kw)
        return _Answer()

    monkeypatch.setattr(inference, "generate", fake_generate)
    drawn = evaluation_run._settle_scenario(_Context(), _commission())
    assert drawn == "Una clínica veterinaria gestiona citas y vacunas."
    assert len(calls) == 1
    assert calls[0]["model"] == "el-rapido"
    assert calls[0]["think"] is False
    assert calls[0]["temperature"] > 0


def test_a_failed_draw_leaves_the_scenario_empty(monkeypatch):
    def broken(**kw):
        raise RuntimeError("engine down")

    monkeypatch.setattr(inference, "generate", broken)
    assert evaluation_run._settle_scenario(_Context(), _commission()) == ""


def test_a_drawn_scenario_is_capped():
    assert len(evaluation_run._first_sentence("x" * 1000)) == evaluation_run.SCENARIO_MAX_CHARS


# THE RECORD ------------------------------------------------------------------------------


def test_the_scenario_round_trips_through_the_trace():
    session = EvaluationSession(
        id="s1", created_at=0.0, concepts=["Bucles"], item_type="ejercicio", fixed={}, curriculum=[],
        instructions="", seed=1, shuffle=["system", "rag"], arms={}, scenario="Una tienda de té",
    )
    assert EvaluationSession.from_dict(session.to_dict()).scenario == "Una tienda de té"
    assert EvaluationSession.from_dict({"id": "old", "created_at": 0.0}).scenario == ""


def test_the_csv_carries_the_scenario():
    text = evaluation_store.export_csv([])
    assert "scenario" in text.splitlines()[0].split(",")
