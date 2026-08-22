import json

import pytest

from variant_generator.settings import store
from variant_generator.settings.types import Impact, Setting, SettingError


def make(key, name, kind, default, **kw):
    return Setting(
        key=key,
        name=name,
        kind=kind,
        default=default,
        group="G",
        doc="Una razón medida.",
        impact=Impact.NONE,
        **kw,
    )


SETTINGS = [
    make("models.main", "LLM_MAIN", "str", "modelo-por-defecto"),
    make("engine.idle", "IDLE", "int", 1800, env="VG_IDLE"),
    make("evaluation.keys.groq", "", "str", "", secret=True, env="GROQ_KEY"),
    make("models.phases.repair", "REPAIR_LLM", "str", None, nullable=True),
]


def test_nesting_and_flattening_round_trip():
    flat = {"models.main": "x", "models.phases.repair": "y", "engine.idle": 5}
    assert store.nest(flat) == {
        "models": {"main": "x", "phases": {"repair": "y"}},
        "engine": {"idle": 5},
    }


def test_read_file_flattens(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"models": {"main": "del fichero"}}), encoding="utf-8")
    assert store.read_file(path) == {"models.main": "del fichero"}


def test_read_file_on_a_missing_file_is_empty(tmp_path):
    assert store.read_file(tmp_path / "no-existe") == {}


def test_read_file_on_broken_json_is_empty_and_does_not_raise(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{no soy json", encoding="utf-8")
    assert store.read_file(path) == {}


def test_precedence_default_then_file_then_env():
    values, sources = store.resolve(
        SETTINGS,
        {"models.main": "del fichero", "engine.idle": 900},
        {"VG_IDLE": "60"},
    )
    assert values["models.main"] == "del fichero"
    assert sources["models.main"] == "file"
    assert values["engine.idle"] == 60
    assert sources["engine.idle"] == "env"
    assert values["models.phases.repair"] is None
    assert sources["models.phases.repair"] == "default"


def test_an_unknown_key_in_the_file_is_ignored_and_does_not_raise():
    values, _ = store.resolve(SETTINGS, {"no.existe": 1}, {})
    assert "no.existe" not in values
    assert values["models.main"] == "modelo-por-defecto"


def test_an_invalid_value_in_the_file_falls_back_to_the_default():
    values, sources = store.resolve(SETTINGS, {"engine.idle": "no soy un número"}, {})
    assert values["engine.idle"] == 1800
    assert sources["engine.idle"] == "default"


def test_an_empty_environment_variable_does_not_override():
    values, sources = store.resolve(SETTINGS, {"engine.idle": 900}, {"VG_IDLE": ""})
    assert values["engine.idle"] == 900
    assert sources["engine.idle"] == "file"


def test_write_file_omits_secrets(tmp_path):
    path = tmp_path / "config.json"
    values = {
        "models.main": "x",
        "engine.idle": 5,
        "evaluation.keys.groq": "SECRETO",
        "models.phases.repair": None,
    }
    store.write_file(path, SETTINGS, values)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["models"]["main"] == "x"
    assert written["models"]["phases"]["repair"] is None
    assert "keys" not in written.get("evaluation", {})
    assert "SECRETO" not in path.read_text(encoding="utf-8")


def test_write_then_read_round_trips(tmp_path):
    path = tmp_path / "config.json"
    values, _ = store.resolve(SETTINGS, {}, {})
    store.write_file(path, SETTINGS, values)
    again, _ = store.resolve(SETTINGS, store.read_file(path), {})
    assert again["models.main"] == values["models.main"]
    assert again["models.phases.repair"] is None


def test_validate_patch_rejects_the_whole_patch_on_one_bad_value():
    with pytest.raises(SettingError):
        store.validate_patch(SETTINGS, {"models.main": "ok", "engine.idle": "nope"})


def test_validate_patch_returns_coerced_values():
    assert store.validate_patch(SETTINGS, {"engine.idle": "42"}) == {"engine.idle": 42}


def test_validate_patch_refuses_a_locked_setting():
    locked = [make("a.b", "AB", "int", 1, editable=False)]
    with pytest.raises(SettingError, match="AB"):
        store.validate_patch(locked, {"a.b": 2})


def test_validate_patch_refuses_an_unknown_key():
    with pytest.raises(SettingError, match="no.existe"):
        store.validate_patch(SETTINGS, {"no.existe": 1})


def test_validate_patch_names_every_offender_not_just_the_first():
    with pytest.raises(SettingError) as caught:
        store.validate_patch(SETTINGS, {"engine.idle": "nope", "no.existe": 1})
    message = str(caught.value)
    assert "IDLE" in message
    assert "no.existe" in message
