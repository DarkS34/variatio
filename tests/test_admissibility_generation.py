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
