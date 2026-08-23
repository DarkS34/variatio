import copy

from variant_generator.instance.exemplars_profile import profile_drift

EMPTY = {"added": [], "removed": [], "changed": []}


def _profile() -> dict:
    return {
        "item_types": {
            "test": {
                "primary_field": "enunciado",
                "fields": {
                    "enunciado": {"schema": {"type": "string"}},
                    "opciones": {"schema": {"type": "array", "items": {"type": "string"}}},
                    "nivel_dificultad": {
                        "schema": {"enum": ["baja", "media", "alta"]},
                        "decided_by": "user",
                    },
                },
            },
            "codigo": {
                "primary_field": "enunciado",
                "fields": {
                    "enunciado": {"schema": {"type": "string"}},
                    "nivel_dificultad": {
                        "schema": {"enum": ["baja", "media", "alta"]},
                        "decided_by": "user",
                    },
                },
            },
        }
    }


def test_equal_profiles_have_no_drift():
    assert profile_drift(_profile(), copy.deepcopy(_profile())) == EMPTY


def test_an_added_field_names_its_modalities():
    draft = _profile()
    draft["item_types"]["test"]["fields"]["pista"] = {"schema": {"type": "string"}}
    drift = profile_drift(_profile(), draft)
    assert drift["added"] == [{"field": "pista", "item_types": ["test"]}]
    assert drift["removed"] == [] and drift["changed"] == []


def test_a_removed_field_counts_every_modality_it_left():
    draft = _profile()
    del draft["item_types"]["test"]["fields"]["opciones"]
    drift = profile_drift(_profile(), draft)
    assert drift["removed"] == [
        {"field": "opciones", "item_types": ["test"], "decided_by": "model"}
    ]


def test_a_removed_user_decided_field_says_so():
    draft = _profile()
    for spec in draft["item_types"].values():
        del spec["fields"]["nivel_dificultad"]
    drift = profile_drift(_profile(), draft)
    assert drift["removed"] == [
        {"field": "nivel_dificultad", "item_types": ["codigo", "test"], "decided_by": "user"}
    ]


def test_a_changed_type_is_reported_with_its_aspect():
    draft = _profile()
    draft["item_types"]["test"]["fields"]["opciones"]["schema"] = {"type": "string"}
    drift = profile_drift(_profile(), draft)
    assert drift["changed"] == [{"field": "opciones", "item_types": ["test"], "aspects": ["type"]}]


def test_enum_and_decided_by_changes_are_aspects_too():
    draft = _profile()
    spec = draft["item_types"]["test"]["fields"]["nivel_dificultad"]
    spec["schema"]["enum"] = ["baja", "alta"]
    spec.pop("decided_by")
    drift = profile_drift(_profile(), draft)
    assert drift["changed"] == [
        {"field": "nivel_dificultad", "item_types": ["test"], "aspects": ["enum", "decided_by"]}
    ]


def test_a_dropped_modality_removes_all_its_fields():
    draft = _profile()
    del draft["item_types"]["codigo"]
    drift = profile_drift(_profile(), draft)
    assert {entry["field"] for entry in drift["removed"]} == {"enunciado", "nivel_dificultad"}
    assert all(entry["item_types"] == ["codigo"] for entry in drift["removed"])


def test_description_and_guidance_edits_are_not_drift():
    draft = _profile()
    draft["item_types"]["test"]["fields"]["enunciado"]["guidance"] = {"extraction": "x"}
    draft["item_types"]["test"]["fields"]["enunciado"]["description"] = "otra"
    assert profile_drift(_profile(), draft) == EMPTY
