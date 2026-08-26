import pytest

from variant_generator import admissibility
from variant_generator.prompts import generate_content_prompt

BLOCKS = dict(
    context_block="", item_type_block="t", target_concepts_block="c",
    prerequisites_block="", excluded_concepts_block="", curriculum_block="",
    rules_block="r", few_shot_block="", already_generated=[],
    instance_template="{}", fields_block="f", fixed_values_block="",
)


def test_the_prompt_renders_one_line_per_typed_request():
    requests = (
        admissibility.Request(text="una panadería", slot="ambito", owner=None, term=None),
        admissibility.Request(text="breve", slot="extension", owner=None, term=None),
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
    from variant_generator.prompts.generation import _SLOT_LABELS

    assert _SLOT_LABELS == {s.key: s.label for s in admissibility.CATALOG}


def _bare_generator(context):
    from variant_generator import variant_generator as vg

    generator = vg.VariantGenerator.__new__(vg.VariantGenerator)
    generator.content_context = context
    generator._screen_instructions_owners = lambda item_type, concepts: []
    return generator


def test_generate_screens_the_guardrail_before_the_classifier(context, monkeypatch):
    from variant_generator import guardrail

    order = []
    monkeypatch.setattr(
        guardrail,
        "check",
        lambda text, *a, **k: order.append("guardrail") or guardrail.Verdict(None, True),
    )
    monkeypatch.setattr(
        admissibility,
        "screen",
        lambda *a, **k: order.append("admissibility") or admissibility.Ruling((), True),
    )
    _bare_generator(context)._screen_instructions(None, ["Recursividad"], "que vaya de deporte")
    assert order == ["guardrail", "admissibility"]


def test_generate_raises_naming_the_owner_and_the_term(context, monkeypatch):
    from variant_generator import guardrail

    owner = admissibility.Owner(
        key="field:nivel_dificultad",
        label="nivel_dificultad",
        where="decídelo en «¿Cómo debe ser?»",
        terms=("avanzado",),
    )
    monkeypatch.setattr(guardrail, "check", lambda text, *a, **k: guardrail.Verdict(None, True))
    monkeypatch.setattr(
        admissibility,
        "screen",
        lambda *a, **k: admissibility.Ruling(
            (admissibility.Request("muy difícil", None, owner, "avanzado"),), True
        ),
    )
    with pytest.raises(ValueError) as excinfo:
        _bare_generator(context)._screen_instructions(None, ["Recursividad"], "muy difícil")
    message = str(excinfo.value)
    assert "muy difícil" in message
    assert "nivel_dificultad" in message
    assert "¿Cómo debe ser?" in message
