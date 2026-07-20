import json
from typing import Literal

import pytest
from pydantic import ValidationError

from system.content_profile import ContentProfile


def test_loads_declared_sections(profile):
    assert profile.content_context["materia"] == "Programación I"
    assert len(profile.general_generation_rules) == 2
    assert profile.primary_field == "statement"
    assert set(profile.field_specs) == {
        "statement",
        "solution",
        "difficulty_level",
        "points",
        "tags",
    }


def test_content_item_exposes_the_primary_field(profile):
    assert profile.content_item.PRIMARY_FIELD == "statement"


def test_general_generation_rules_is_copied_not_aliased(profile, min_profile_data):
    profile.general_generation_rules.append("regla intrusa")

    assert len(min_profile_data["general_generation_rules"]) == 2


# VALIDATION ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda p: p.pop("fields"), "missing required keys"),
        (lambda p: p.pop("primary_field"), "missing required keys"),
        (lambda p: p.update(content_context={}), "non-empty object"),
        (lambda p: p.update(content_context="Programación"), "non-empty object"),
        (lambda p: p.update(general_generation_rules="una regla"), "must be a list"),
        (lambda p: p.update(fields={}), "non-empty object"),
        (lambda p: p.update(primary_field=3), "must be a string"),
        (lambda p: p.update(primary_field="ausente"), "is not declared in"),
        (lambda p: p["fields"].update(statement="no soy un objeto"), "spec must be an object"),
        (lambda p: p["fields"]["statement"].pop("schema"), "non-empty 'schema' object"),
        (lambda p: p["fields"]["statement"].update(schema={}), "non-empty 'schema' object"),
        (
            lambda p: p["fields"]["statement"].update(schema={"minLength": 3}),
            "must declare 'type' or 'enum'",
        ),
        (
            lambda p: p["fields"]["statement"].update(guidance="extrae el enunciado"),
            "'guidance' must be an object",
        ),
        (
            lambda p: p["fields"]["statement"]["guidance"].update(traduccion="al inglés"),
            "unknown keys",
        ),
    ],
)
def test_validation_rejects_malformed_profiles(write_profile, min_profile_data, mutate, expected):
    mutate(min_profile_data)

    with pytest.raises(ValueError, match=expected):
        write_profile(min_profile_data)


def test_validation_rejects_a_non_object_root(write_profile):
    with pytest.raises(ValueError, match="root must be an object"):
        write_profile(["no", "soy", "un", "perfil"])


def test_a_field_may_omit_guidance_entirely(write_profile, min_profile_data):
    min_profile_data["fields"]["statement"].pop("guidance")
    profile = write_profile(min_profile_data)

    assert profile.field_guidance("extraction").keys() == {"solution", "difficulty_level"}
    assert profile.field_guidance("generation").keys() == {"solution"}


# TYPE MAPPING -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema, expected",
    [
        ({"type": "string"}, str),
        ({"type": "integer"}, int),
        ({"type": "number"}, float),
        ({"type": "boolean"}, bool),
        ({"type": "null"}, type(None)),
        ({"type": "object"}, dict),
        ({"type": ["string", "null"]}, str | None),
        ({"type": ["string", "integer", "null"]}, str | int | None),
        ({"type": "array"}, list[str]),
        ({"type": "array", "items": {"type": "integer"}}, list[int]),
        (
            {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            list[list[str]],
        ),
        ({"enum": ["a", "b"]}, Literal["a", "b"]),
        ({"enum": ["a", None]}, Literal["a", None]),
    ],
)
def test_py_type_maps_schema_to_python(schema, expected):
    assert ContentProfile._py_type(schema) == expected


def test_enum_wins_over_type_when_both_are_declared():
    assert ContentProfile._py_type({"type": "string", "enum": ["a"]}) == Literal["a"]


@pytest.mark.parametrize(
    "schema, expected",
    [
        ({"enum": []}, "non-empty list"),
        ({"enum": "a"}, "non-empty list"),
        ({"type": []}, "non-empty"),
        ({"type": "date"}, "Unsupported scalar type"),
        ({"type": ["string", "date"]}, "Unsupported scalar type"),
    ],
)
def test_py_type_rejects_unsupported_schemas(schema, expected):
    with pytest.raises(ValueError, match=expected):
        ContentProfile._py_type(schema)


# GENERATED MODEL ----------------------------------------------------------------------------


def test_constraints_reach_the_generated_model(profile):
    properties = profile.content_item.model_json_schema()["properties"]

    assert properties["statement"]["minLength"] == 10
    assert properties["statement"]["maxLength"] == 2000
    assert properties["points"]["minimum"] == 0
    assert properties["points"]["maximum"] == 10


def test_a_schema_default_makes_the_field_optional(profile):
    schema = profile.content_item.model_json_schema()

    assert schema["properties"]["points"]["default"] == 1
    assert "points" not in schema["required"]


def test_fields_without_default_are_required(profile):
    required = set(profile.content_item.model_json_schema()["required"])

    assert required == {"statement", "solution", "difficulty_level", "tags"}


def test_accepts_a_well_formed_item(profile):
    item = profile.content_item(
        statement="Escribe una función que sume dos números enteros.",
        solution="def suma(a, b):\n    return a + b",
        difficulty_level="básico",
        tags=["funciones"],
    )

    assert item.points == 1
    assert item.solution.startswith("def suma")


def test_a_nullable_field_still_has_to_be_present(profile):
    with pytest.raises(ValidationError, match="solution"):
        profile.content_item(
            statement="Escribe una función que sume dos números enteros.",
            difficulty_level="básico",
            tags=["funciones"],
        )


def test_a_nullable_field_accepts_an_explicit_null(profile):
    item = profile.content_item(
        statement="Escribe una función que sume dos números enteros.",
        solution=None,
        difficulty_level=None,
        tags=[],
    )

    assert item.solution is None
    assert item.difficulty_level is None


def test_enum_rejects_a_value_outside_the_declared_set(profile):
    with pytest.raises(ValidationError, match="difficulty_level"):
        profile.content_item(
            statement="Escribe una función que sume dos números enteros.",
            solution=None,
            difficulty_level="imposible",
            tags=[],
        )


def test_constraints_are_enforced_at_validation_time(profile):
    with pytest.raises(ValidationError, match="statement"):
        profile.content_item(
            statement="corto", solution=None, difficulty_level=None, tags=[]
        )


# DERIVED VIEWS ------------------------------------------------------------------------------


def test_stripped_schema_drops_guidance_from_every_property(profile):
    stripped = profile.stripped_schema()

    assert all("guidance" not in prop for prop in stripped["properties"].values())
    assert "guidance" in profile.content_item.model_json_schema()["properties"]["statement"]


def test_stripped_schema_does_not_mutate_the_model(profile):
    profile.stripped_schema()

    assert "guidance" in profile.content_item.model_json_schema()["properties"]["statement"]


def test_stripped_schema_shape(profile, assert_snapshot):
    assert_snapshot(
        "stripped_schema",
        json.dumps(profile.stripped_schema(), indent=2, ensure_ascii=False, sort_keys=True),
    )


def test_field_guidance_splits_by_task(profile):
    assert profile.field_guidance("generation").keys() == {"statement", "solution"}
    assert profile.field_guidance("extraction").keys() == {
        "statement",
        "solution",
        "difficulty_level",
    }


def test_field_guidance_rejects_an_unknown_task(profile):
    with pytest.raises(ValueError, match="Unknown task"):
        profile.field_guidance("traduccion")
