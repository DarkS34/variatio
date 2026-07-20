import random

import pytest

ITEM_OK = (
    '{"statement": "Escribe una función que recorra una lista.", "solution": null, '
    '"difficulty_level": "básico", "tags": []}'
)


def _example(statement: str, **overrides) -> dict:
    base = {
        "statement": statement,
        "solution": "def f(): pass",
        "difficulty_level": "básico",
        "points": 3,
        "tags": ["listas"],
        "concepts": ["Bucles"],
    }
    return {**base, **overrides}


# INPUT VALIDATION ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"concepts": ["Bucles"], "n": 0}, "n must be >= 1"),
        ({"concepts": []}, "non-empty list"),
        ({"concepts": ["Inventado"]}, "Unknown concepts"),
        ({"concepts": ["Programación"]}, "Unknown concepts"),
        ({"concepts": ["Bucles"], "fixed": {"inexistente": 1}}, "Unknown fixed fields"),
        (
            {"concepts": ["Bucles"], "curriculum": ["Inventado"]},
            "Unknown curriculum concepts",
        ),
        (
            {"concepts": ["Bucles"], "curriculum": ["Variables"]},
            "not contained in curriculum",
        ),
    ],
)
def test_generate_rejects_invalid_input(generator, kwargs, expected):
    with pytest.raises(ValueError, match=expected):
        generator.generate(**kwargs)


def test_non_taggable_concepts_are_not_valid_targets(generator, kg):
    assert "Programación" in kg.all_concepts
    assert "Programación" not in generator.taggable_concepts


def test_a_curriculum_containing_the_targets_is_accepted(generator, scripted_generate):
    scripted_generate(ITEM_OK)

    results = generator.generate(concepts=["Bucles"], curriculum=["Bucles", "Variables"])

    assert len(results) == 1


# FEW-SHOT SELECTION -------------------------------------------------------------------------


def test_few_shot_only_uses_examples_sharing_a_target_concept(generator):
    generator.exemplars_bank = {
        "C001": _example("comparte", concepts=["Bucles"]),
        "C002": _example("no comparte", concepts=["Variables"]),
    }

    picked = generator._select_few_shot(["Bucles"], {})

    assert [p["statement"] for p in picked] == ["comparte"]


def test_few_shot_is_capped_at_the_configured_maximum(generator):
    generator.exemplars_bank = {f"C{i:03d}": _example(f"ejemplo {i}") for i in range(20)}
    random.seed(0)

    picked = generator._select_few_shot(["Bucles"], {})

    assert len(picked) == generator.max_few_shot


def test_few_shot_narrows_to_fixed_values_when_enough_examples_match(generator):
    generator.exemplars_bank = {
        **{f"B{i}": _example(f"básico {i}", difficulty_level="básico") for i in range(6)},
        **{f"A{i}": _example(f"avanzado {i}", difficulty_level="avanzado") for i in range(6)},
    }
    random.seed(0)

    picked = generator._select_few_shot(["Bucles"], {"difficulty_level": "básico"})

    assert all(p["difficulty_level"] == "básico" for p in picked)


def test_few_shot_ignores_the_fixed_filter_when_too_few_examples_match(generator):
    generator.exemplars_bank = {
        "B0": _example("básico", difficulty_level="básico"),
        **{f"A{i}": _example(f"avanzado {i}", difficulty_level="avanzado") for i in range(6)},
    }
    random.seed(0)

    picked = generator._select_few_shot(["Bucles"], {"difficulty_level": "básico"})

    assert any(p["difficulty_level"] == "avanzado" for p in picked)


def test_few_shot_is_empty_without_matching_examples(generator):
    generator.exemplars_bank = {"C001": _example("otro", concepts=["Variables"])}

    assert generator._select_few_shot(["Bucles"], {}) == []


# THINKING SPLIT -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, sdk, body, thinking",
    [
        ("cuerpo", None, "cuerpo", None),
        ("<think>razono</think>cuerpo", None, "cuerpo", "razono"),
        ("cuerpo", "del sdk", "cuerpo", "del sdk"),
        ("<think>inline</think>cuerpo", "del sdk", "cuerpo", "del sdk\n\ninline"),
        ("<THINK>mayúsculas</THINK>cuerpo", None, "cuerpo", "mayúsculas"),
        ("<think>a</think>x<think>b</think>y", None, "xy", "a\n\nb"),
        ("", None, "", None),
    ],
)
def test_split_thinking(generator, raw, sdk, body, thinking):
    assert generator._split_thinking(raw, sdk) == (body, thinking)


# PROMPT BLOCKS ------------------------------------------------------------------------------


def test_target_concepts_block_uses_the_concept_descriptions(generator):
    generator.embedder.concept_descriptions = {"Bucles": "itera sobre secuencias"}

    block = generator._format_target_concepts(["Bucles", "Variables"])

    assert block == "- **Bucles**: itera sobre secuencias\n- **Variables**"


def test_instance_template_marks_fixed_and_free_fields(generator, assert_snapshot):
    assert_snapshot(
        "instance_template",
        generator._build_instance_template({"difficulty_level": "intermedio"}),
    )


def test_fixed_values_block(generator, assert_snapshot):
    assert_snapshot(
        "fixed_values_block",
        generator._build_fixed_values_block({"difficulty_level": "intermedio", "points": 5}),
    )


def test_fixed_values_block_without_fixed_values(generator):
    assert generator._build_fixed_values_block({}) == "(no hay valores fijos)"


def test_field_guidance_block_omits_fields_already_fixed(generator):
    block = generator._build_field_guidance_block({"solution": "x"})

    assert "`statement`" in block
    assert "`solution`" not in block


def test_field_guidance_block_when_everything_is_fixed(generator):
    block = generator._build_field_guidance_block({"statement": "x", "solution": "y"})

    assert block.startswith("(ningún campo con guía")


def test_few_shot_block_layout(generator, assert_snapshot):
    assert_snapshot(
        "few_shot_block",
        generator._build_few_shot_block([_example("Recorre una lista de precios.")]),
    )


def test_few_shot_block_is_empty_without_examples(generator):
    assert generator._build_few_shot_block([]) == ""


def test_already_generated_collects_the_primary_field(generator, scripted_generate):
    scripted_generate(ITEM_OK, ITEM_OK)
    results = generator.generate(concepts=["Bucles"], n=2)

    collected = generator._collect_already_generated(results)

    assert collected == ["Escribe una función que recorra una lista."] * 2


# GENERATION LOOP ----------------------------------------------------------------------------


def test_generate_produces_the_requested_number_of_items(generator, scripted_generate):
    scripted_generate(ITEM_OK, ITEM_OK, ITEM_OK)

    assert len(generator.generate(concepts=["Bucles"], n=3)) == 3


def test_generate_keeps_going_after_an_unrecoverable_item(generator, scripted_generate):
    scripted_generate(*(["roto"] * 4), ITEM_OK)

    results = generator.generate(concepts=["Bucles"], n=2)

    assert len(results) == 1


def test_generate_applies_the_fixed_values_to_the_item(generator, scripted_generate):
    scripted_generate(ITEM_OK)

    results = generator.generate(concepts=["Bucles"], n=1, fixed={"difficulty_level": "avanzado"})

    assert results[0].item.difficulty_level == "avanzado"


def test_generate_feeds_previous_items_back_into_the_prompt(generator, scripted_generate):
    calls = scripted_generate(ITEM_OK, ITEM_OK)

    generator.generate(concepts=["Bucles"], n=2)

    assert "YA GENERADOS EN ESTE LOTE" not in calls[0]["prompt"]
    assert "YA GENERADOS EN ESTE LOTE" in calls[1]["prompt"]


def test_generate_repairs_with_the_injected_model(kg, profile, stub_embedder, scripted_generate):
    from system.content_generator import ContentGenerator

    generator = ContentGenerator(
        knowledge_graph=kg,
        exemplars_bank={},
        embedder=stub_embedder([]),
        content_profile=profile,
        generator_model="gen",
        repair_model="reparador",
    )
    calls = scripted_generate("roto", ITEM_OK)

    generator.generate(concepts=["Bucles"], n=1)

    assert [c["model"] for c in calls] == ["gen", "reparador"]
