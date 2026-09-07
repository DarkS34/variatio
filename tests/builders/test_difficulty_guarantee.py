"""The one field every modality carries, and the ladder they all share.

Difficulty is the axis a commission turns and the axis the bank is sorted along, so it is
not a field the consolidation may or may not invent. The prompt asks for it in a section of
its own; `guarantee_difficulty` is what makes it true whatever the answer looked like.

The shapes exercised here are not hypothetical. Measured on the real builds of two
workspaces: the model converges on the field and on the three rungs by itself, but one
draft wrote `básico` with its accent — a different stored value from the same builder on
the same corpus — and none of the four drafts set `decided_by`.
"""

import pytest

from variatio import prompts
from variatio.builders.exemplars_profile_builder import guarantee_difficulty
from variatio.core import languages
from variatio.instance.exemplars_profile import ExemplarsProfile

SETS = {code: prompts.of(code) for code in languages.LANGUAGES}


def _profile(**fields_by_type) -> dict:
    return {
        "item_types": {
            key: {
                "label": key,
                "primary_field": "enunciado",
                "fields": {"enunciado": {"schema": {"type": "string"}}, **extra},
            }
            for key, extra in fields_by_type.items()
        }
    }


def _field(profile: dict, type_key: str, code: str) -> dict:
    return profile["item_types"][type_key]["fields"][SETS[code].DIFFICULTY_FIELD]


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_a_modality_with_no_difficulty_gets_one(code):
    out = guarantee_difficulty(_profile(escritura={}), SETS[code])
    entry = _field(out, "escritura", code)
    assert entry["schema"]["enum"] == list(SETS[code].DIFFICULTY_LEVELS)
    assert entry["decided_by"] == "user"
    assert entry["description"] == SETS[code].DIFFICULTY_FALLBACK_DESCRIPTION
    assert entry["guidance"]["extraction"] == SETS[code].DIFFICULTY_FALLBACK_EXTRACTION


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_every_modality_gets_the_same_ladder(code):
    out = guarantee_difficulty(_profile(uno={}, dos={}, tres={}), SETS[code])
    ladders = {
        tuple(_field(out, key, code)["schema"]["enum"]) for key in out["item_types"]
    }
    assert ladders == {tuple(SETS[code].DIFFICULTY_LEVELS)}, "the ladder is what is shared"


def test_an_accented_rung_folds_onto_the_canonical_one_and_keeps_its_criterion():
    # The exact draft this project produced: `básico` with its accent, so two builds of the
    # same corpus stored two different values for one rung.
    criterion = "basico (una sola formula), intermedio (bucles), avanzado (recursividad)"
    profile = _profile(
        programacion={
            "nivel_dificultad": {
                "schema": {"enum": ["básico", "intermedio", "avanzado"]},
                "description": criterion,
            }
        }
    )
    entry = _field(guarantee_difficulty(profile, SETS["es"]), "programacion", "es")
    assert entry["schema"]["enum"] == ["basico", "intermedio", "avanzado"]
    assert entry["description"] == criterion, "folding a rung loses nothing, so nothing is lost"


def test_a_criterion_the_model_wrote_is_never_replaced():
    profile = _profile(
        test={"nivel_dificultad": {"schema": {"enum": ["basico", "intermedio", "avanzado"]},
                                   "description": "el criterio de esta modalidad",
                                   "guidance": {"extraction": "la etiqueta del documento"}}}
    )
    entry = _field(guarantee_difficulty(profile, SETS["es"]), "test", "es")
    assert entry["description"] == "el criterio de esta modalidad"
    assert entry["guidance"]["extraction"] == "la etiqueta del documento"


def test_a_ladder_that_does_not_fold_is_replaced_and_the_criterion_survives_for_a_human():
    # Dropping it would throw away the modality's only reasoning; the profile screen now
    # draws it where somebody will see that it describes rungs that are gone.
    profile = _profile(
        raro={"nivel_dificultad": {"schema": {"enum": ["1", "2", "3", "4", "5"]},
                                   "description": "cinco peldanos"}}
    )
    entry = _field(guarantee_difficulty(profile, SETS["es"]), "raro", "es")
    assert entry["schema"]["enum"] == ["basico", "intermedio", "avanzado"]
    assert entry["description"] == "cinco peldanos"


def test_the_other_language_s_name_is_renamed_rather_than_duplicated():
    profile = _profile(
        escritura={"difficulty_level": {"schema": {"enum": ["basic", "intermediate", "advanced"]},
                                        "description": "written under the other set's name"}}
    )
    fields = guarantee_difficulty(profile, SETS["es"])["item_types"]["escritura"]["fields"]
    assert "difficulty_level" not in fields, "one difficulty per modality, not two"
    assert fields["nivel_dificultad"]["description"] == "written under the other set's name"


def test_it_is_dropped_from_embed_fields():
    # It carries no concept and adds the same noise to every item, so indexing it can only
    # push retrieval towards whatever else the text happens to share.
    profile = _profile(escritura={"nivel_dificultad": {"schema": {"enum": ["basico"]}}})
    profile["item_types"]["escritura"]["embed_fields"] = ["enunciado", "nivel_dificultad"]
    out = guarantee_difficulty(profile, SETS["es"])
    assert out["item_types"]["escritura"]["embed_fields"] == ["enunciado"]


def test_it_is_written_last_so_the_artifact_reads_as_the_screens_draw_it():
    profile = _profile(escritura={"solucion": {"schema": {"type": ["string", "null"]}}})
    fields = list(guarantee_difficulty(profile, SETS["es"])["item_types"]["escritura"]["fields"])
    assert fields[-1] == "nivel_dificultad"


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_what_it_writes_loads(code):
    out = guarantee_difficulty(_profile(uno={}), SETS[code])
    ExemplarsProfile.validate_raw(out)


def test_a_modality_that_is_not_an_object_is_left_for_the_validator():
    # `_validate` reports it with the message it already has; guessing here would replace
    # one clear error with a confusing one.
    profile = {"item_types": {"roto": "no soy un objeto"}}
    assert guarantee_difficulty(profile, SETS["es"]) == profile
