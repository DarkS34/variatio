import json

from variatio import admissibility
from variatio.core.lexicon import fold
from variatio.instance.exemplars_profile import ExemplarsProfile

from ..conftest import PROFILE


def _owner(owners, key):
    return next(o for o in owners if o.key == key)


def test_fold_strips_accents_and_case():
    assert fold("Recursividad Básica") == "recursividad basica"


def test_owners_lists_every_concept_except_the_targets(owners_for):
    found = owners_for()
    concepts = _owner(found, "concepts")
    assert "Recursividad" not in concepts.terms
    assert "Variable" in concepts.terms
    assert "Función" in concepts.terms


def test_owners_carries_the_enum_of_a_user_decided_field(owners_for):
    found = owners_for()
    field = _owner(found, "field:nivel_dificultad")
    assert field.terms == ("basico", "intermedio", "avanzado")
    assert field.label == "nivel_dificultad"


def test_a_type_without_user_decided_fields_produces_no_field_owner(owners_for):
    found = owners_for(item_type="analisis")
    assert not [o for o in found if o.key.startswith("field:")]


def test_owners_carries_the_modalities_and_the_three_facts(owners_for):
    found = owners_for()
    assert "Análisis de código" in _owner(found, "item_type").terms
    assert "castellano" in _owner(found, "context").terms
    assert "Programación en Python" in _owner(found, "context").terms


def test_catalog_keys_never_collide_with_owner_keys(owners_for):
    found = owners_for()
    assert not {s.key for s in admissibility.CATALOG} & {o.key for o in found}


def test_every_slot_declares_a_label_and_an_example():
    assert len(admissibility.CATALOG) == 4
    assert all(s.key and s.label and s.example for s in admissibility.CATALOG)


def test_the_difficulty_owns_its_control_without_decided_by(graph, context, tmp_path):
    """A profile built before the ladder became mandatory still owns «hazlo avanzado».

    `decided_by` is absent on four of the six modalities of `cs0-examenes`, and since
    2026-09-01 the generate form offers the rung on those too — it reads the field, not
    that key. The judge has to see the same catalogue the screen does, or the free text
    would be admissible on exactly the instances where the control exists.
    """
    profile_data = json.loads(json.dumps(PROFILE))
    del profile_data["item_types"]["ejercicio"]["fields"]["nivel_dificultad"]["decided_by"]
    path = tmp_path / "older_profile.json"
    path.write_text(json.dumps(profile_data, ensure_ascii=False), encoding="utf-8")
    older = ExemplarsProfile(path)

    found = admissibility.owners(
        graph, older.item_type("ejercicio"), older, context, ["Recursividad"]
    )
    field = _owner(found, "field:nivel_dificultad")
    assert field.terms == ("basico", "intermedio", "avanzado")
    assert "nivel" in field.where
