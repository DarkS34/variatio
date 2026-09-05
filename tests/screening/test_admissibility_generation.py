import pytest

from variatio.runtime import screening
from variatio.runtime.screening import admissibility
from variatio.prompts.es import generate_content_prompt

from ..conftest import ES

BLOCKS = dict(
    context_block="", item_type_block="t", target_concepts_block="c",
    prerequisites_block="", excluded_concepts_block="", curriculum_block="",
    rules_block="r", few_shot_block="", already_generated=[],
    instance_template="{}", fields_block="f", fixed_values_block="",
)


def test_the_prompt_renders_one_line_per_typed_request():
    requests = (
        screening.Request(text="una panadería", slot="ambito", owner=None, term=None),
        screening.Request(text="breve", slot="extension", owner=None, term=None),
    )
    prompt = generate_content_prompt(**BLOCKS, instructions="da igual", requests=requests)
    assert "- Ámbito: una panadería" in prompt
    assert "- Extensión: breve" in prompt
    assert "da igual" not in prompt


def test_the_prompt_falls_back_to_the_raw_text_without_a_ruling():
    prompt = generate_content_prompt(**BLOCKS, instructions="que vaya de deporte", requests=None)
    assert "que vaya de deporte" in prompt


def test_the_prompt_has_no_petition_section_without_instructions():
    prompt = generate_content_prompt(**BLOCKS, instructions="", requests=None)
    assert "PETICIÓN DE QUIEN PIDE EL EJERCICIO" not in prompt


def test_the_prompt_labels_match_the_catalog():
    from variatio.prompts.es.generation import _SLOT_LABELS

    assert _SLOT_LABELS == {s.key: s.label for s in screening.catalog()}


def _screen(context, graph, profile, instructions):
    """Run the shared screening sequence the generator and the evaluation both call."""
    return screening.screen_instructions(
        instructions,
        knowledge_graph=graph,
        item_type=profile.item_type("ejercicio"),
        profile=profile,
        content_context=context,
        concepts=["Recursividad"],
        prompts=ES,
    )


def test_generate_screens_the_guardrail_before_the_classifier(context, graph, profile, monkeypatch):
    from variatio.runtime.screening import guardrail

    order = []
    monkeypatch.setattr(
        guardrail,
        "check",
        lambda text, *a, **k: order.append("guardrail") or guardrail.Verdict(None, True),
    )
    monkeypatch.setattr(
        admissibility,
        "screen",
        lambda *a, **k: order.append("admissibility") or screening.Ruling((), True),
    )
    _screen(context, graph, profile, "que vaya de deporte")
    assert order == ["guardrail", "admissibility"]


def test_generate_raises_naming_the_owner_and_the_term(context, graph, profile, monkeypatch):
    from variatio.runtime.screening import guardrail

    owner = screening.Owner(
        key="field:nivel_dificultad",
        label="nivel_dificultad",
        where="decídelo en «¿Cómo debe ser?»",
        terms=("avanzado",),
    )
    monkeypatch.setattr(guardrail, "check", lambda text, *a, **k: guardrail.Verdict(None, True))
    monkeypatch.setattr(
        admissibility,
        "screen",
        lambda *a, **k: screening.Ruling(
            (screening.Request("muy difícil", None, owner, "avanzado"),), True
        ),
    )
    with pytest.raises(ValueError) as excinfo:
        _screen(context, graph, profile, "muy difícil")
    message = str(excinfo.value)
    assert "muy difícil" in message
    assert "nivel_dificultad" in message
    assert "¿Cómo debe ser?" in message
