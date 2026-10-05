"""A field a commission may leave out: read from the bank, written only when asked for.

`omittable: true` is how whoever prepares a subject says "whoever asks for an exercise
chooses whether it carries this part". The field stays declared — the bank was extracted
with it and is still read with it — so leaving it out cannot be a deletion: it is a second
reading of the same modality, `ItemType.without(names)`, and everything that writes the
new item reads that one.
"""

import json

import pytest

from variatio import wording
from variatio.instance.exemplars_profile import ExemplarsProfile
from variatio.runtime import checks
from variatio.runtime.generator import (
    VariantGenerator,
    build_few_shot_block,
    clean_fixed,
    parse_item,
)
from variatio.runtime.screening import admissibility

from ..conftest import ES


def _profile(tmp_path, **marks) -> ExemplarsProfile:
    fields = {
        "enunciado": {"schema": {"type": "string"}, "description": "El texto."},
        "solucion": {"schema": {"type": "string"}, "description": "La solución."},
        "formato": {"schema": {"enum": ["test", "abierto"]}, "decided_by": "user"},
        "nivel_dificultad": {
            "schema": {"enum": ["basico", "intermedio", "avanzado"]},
            "decided_by": "user",
        },
    }
    for name, omittable in marks.items():
        fields[name] = {**fields[name], "omittable": omittable}
    raw = {
        "item_types": {
            "ejercicio": {
                "primary_field": "enunciado",
                "embed_fields": ["enunciado", "solucion"],
                "fields": fields,
            }
        }
    }
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return ExemplarsProfile(path)


def test_a_commission_that_leaves_nothing_out_reads_the_modality_itself(tmp_path):
    item_type = _profile(tmp_path, solucion=True).item_type("ejercicio")
    assert item_type.omittable_fields == ["solucion"]
    assert item_type.without(None) is item_type
    assert item_type.without([]) is item_type


def test_a_field_left_out_is_gone_from_the_reading_and_stays_in_the_profile(tmp_path):
    full = _profile(tmp_path, solucion=True).item_type("ejercicio")
    reading = full.without(["solucion"])

    assert list(full.field_specs) == ["enunciado", "solucion", "formato", "nivel_dificultad"]
    assert list(reading.field_specs) == ["enunciado", "formato", "nivel_dificultad"]
    assert reading.left_out == ("solucion",)
    assert "solucion" not in reading.stripped_schema()["properties"]
    assert "solucion" not in reading.stripped_schema()["required"]
    # An indexed field that is not written cannot be what the new item is compared by.
    assert reading.embed_fields == ["enunciado"]
    assert reading.key == full.key
    assert full.without(["solucion"]) is reading


def test_only_a_field_the_profile_marks_can_be_left_out(tmp_path):
    full = _profile(tmp_path, solucion=True, formato=False).item_type("ejercicio")
    # A commission saved under an earlier profile is repeated, not refused.
    assert full.without(["formato", "enunciado", "no_existe"]) is full
    assert full.without(["formato", "solucion"]).left_out == ("solucion",)


def test_a_new_item_validates_without_the_field_and_drops_it_if_the_model_writes_it(tmp_path):
    reading = _profile(tmp_path, solucion=True).item_type("ejercicio").without(["solucion"])
    reply = json.dumps(
        {
            "enunciado": "Escribe una función que sume los elementos de una lista de enteros.",
            "solucion": "def suma(xs): return sum(xs)",
            "formato": "abierto",
            "nivel_dificultad": "basico",
        }
    )
    item, error = parse_item(reply, {}, reading)
    assert error is None
    assert "solucion" not in item.model_dump()
    assert checks.content_floor(item, reading) is None


def test_the_prompt_neither_asks_for_the_field_nor_shows_it_in_the_exemplars(tmp_path):
    full = _profile(tmp_path, solucion=True).item_type("ejercicio")
    reading = full.without(["solucion"])
    generator = object.__new__(VariantGenerator)
    generator.prompts = ES
    generator._wording = wording.beside(ES)

    assert "solucion" in generator._build_fields_block(full, {})
    assert "solucion" not in generator._build_fields_block(reading, {})
    assert "solucion" not in generator._build_instance_template(reading, {})
    exemplar = {"enunciado": "Suma dos números.", "solucion": "a + b", "formato": "abierto"}
    assert "a + b" in build_few_shot_block(full, [exemplar])
    assert "a + b" not in build_few_shot_block(reading, [exemplar])


def test_a_choice_left_out_is_no_longer_a_control_the_free_text_is_judged_against(
    tmp_path, graph, context
):
    profile = _profile(tmp_path, formato=True)
    full = profile.item_type("ejercicio")

    def keys(item_type):
        found = admissibility.owners(graph, item_type, profile, context, [])
        return {owner.key for owner in found}

    assert "field:formato" in keys(full)
    assert "field:formato" not in keys(full.without(["formato"]))


def test_a_pin_on_a_field_left_out_is_dropped_and_the_others_are_kept(tmp_path):
    reading = _profile(tmp_path, formato=True).item_type("ejercicio").without(["formato"])
    pins = {"formato": "test", "nivel_dificultad": "basico"}
    assert clean_fixed(pins, reading) == {"nivel_dificultad": "basico"}
    assert clean_fixed(pins) == pins


@pytest.mark.parametrize("name", ["enunciado", "nivel_dificultad"])
def test_the_statement_and_the_difficulty_cannot_be_left_out(tmp_path, name):
    with pytest.raises(ValueError, match="cannot be 'omittable'"):
        _profile(tmp_path, **{name: True})


def test_the_mark_is_a_boolean(tmp_path):
    with pytest.raises(ValueError, match="'omittable' must be true or false"):
        _profile(tmp_path, solucion="yes")
