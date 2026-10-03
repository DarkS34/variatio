import json

import pytest

from variatio.settings import store
from variatio.settings.types import Impact, Setting, SettingError


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
    make("engine.idle", "IDLE", "int", 1800, env="VARIATIO_IDLE"),
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
        {"VARIATIO_IDLE": "60"},
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
    values, sources = store.resolve(SETTINGS, {"engine.idle": 900}, {"VARIATIO_IDLE": ""})
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


# THE RENAMED KEYS ---------------------------------------------------------------------------------
#
# `config.json` at the root is the installation's own settings as they actually stand, and it
# predates the rename of the transcription phase. Refusing to read the old names would turn a
# rename into a silent reset of whatever the installation had chosen.


def test_a_legacy_key_still_resolves(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"models": {"phases": {"exemplars_transcribe": "un-modelo"}}}),
        encoding="utf-8",
    )
    assert store.read_file(path) == {"models.phases.transcribe": "un-modelo"}


def test_a_legacy_key_inside_an_engine_profile_resolves_too(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    "ollama": {
                        "models": {"phases": {"exemplars_transcribe": "un-modelo"}},
                        "reasoning": {
                            "phases": {"exemplars_transcribe": True},
                            "effort": {"exemplars_transcribe": "high"},
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    flat = store.read_file(path)
    assert flat["profiles.ollama.models.phases.transcribe"] == "un-modelo"
    assert flat["profiles.ollama.reasoning.phases.transcribe"] is True
    assert flat["profiles.ollama.reasoning.effort.transcribe"] == "high"
    assert not any("exemplars_transcribe" in key for key in flat)


def test_the_new_name_wins_when_a_file_carries_both(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "models": {
                    "phases": {
                        "exemplars_transcribe": "el-viejo",
                        "transcribe": "el-nuevo",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    assert store.read_file(path)["models.phases.transcribe"] == "el-nuevo"


def test_a_legacy_key_resolves_even_when_resolve_is_called_directly(tmp_path):
    settings = [make("models.phases.transcribe", "TRANSCRIBE_MODEL", "str", None, nullable=True)]
    values, sources = store.resolve(
        settings, {"models.phases.exemplars_transcribe": "un-modelo"}, {}
    )
    assert values["models.phases.transcribe"] == "un-modelo"
    assert sources["models.phases.transcribe"] == "file"


def test_reading_a_legacy_file_and_writing_it_back_migrates_the_name(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"models": {"phases": {"exemplars_transcribe": "un-modelo"}}}),
        encoding="utf-8",
    )
    settings = [make("models.phases.transcribe", "TRANSCRIBE_MODEL", "str", None, nullable=True)]
    values, _ = store.resolve(settings, store.read_file(path), {})
    store.write_file(path, settings, values)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["models"]["phases"] == {"transcribe": "un-modelo"}


# A MAP SETTING IS A VALUE AND NOT A NAMESPACE, and the file cannot tell the two apart on
# its own: `{"gemma-4-31b": "high"}` reads exactly like `{"main": "…"}`. Without the leaf
# set the walk turns one declared key into one undeclared key per entry, so the setting
# reads as absent and every model in it warns.
MAPPED = [
    make("engine.name", "ENGINE", "str", "ollama", choices=("ollama", "hibrido")),
    make(
        "generation.fixed_effort_levels",
        "FIXED_EFFORT_LEVELS",
        "dict[str,str]",
        {},
        scope="engine",
        choices=("low", "high"),
    ),
]


def test_a_map_setting_is_read_whole(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {"profiles": {"hibrido": {"generation": {"fixed_effort_levels": {"gemma": "high"}}}}}
        ),
        encoding="utf-8",
    )
    maps = store.map_keys(MAPPED)
    assert maps == {"generation.fixed_effort_levels"}
    assert store.read_file(path, maps) == {
        "profiles.hibrido.generation.fixed_effort_levels": {"gemma": "high"}
    }
    # And without the leaf set it is exactly the failure the argument exists to prevent.
    assert store.read_file(path) == {
        "profiles.hibrido.generation.fixed_effort_levels.gemma": "high"
    }


def test_a_map_setting_survives_the_round_trip_through_the_file(tmp_path):
    path = tmp_path / "config.json"
    store.write_file(
        path,
        MAPPED,
        {"engine.name": "hibrido"},
        {"hibrido": {"generation.fixed_effort_levels": {"gemma": "high"}}},
    )
    values, _ = store.resolve(MAPPED, store.read_file(path, store.map_keys(MAPPED)), {})
    assert values["generation.fixed_effort_levels"] == {"gemma": "high"}
