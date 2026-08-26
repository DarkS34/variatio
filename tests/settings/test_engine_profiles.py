import json

import pytest

from variant_generator import settings as vg_settings
from variant_generator.settings import store
from variant_generator.settings.types import Impact, Setting


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
    make(
        "engine.name",
        "INFERENCE_ENGINE",
        "str",
        "ollama",
        choices=("ollama", "cerebras+ollama"),
    ),
    make(
        "models.main",
        "LLM_MAIN",
        "str",
        "qwen",
        scope="engine",
        engine_defaults=(("cerebras+ollama", "gemma-4-31b"),),
    ),
    make("models.guardrail", "GUARDRAIL_LLM", "str", "granite", scope="engine"),
    make("engine.idle", "IDLE", "int", 1800),
]


def test_an_engine_scoped_setting_reads_from_the_active_profile():
    values, sources = store.resolve(
        SETTINGS,
        {
            "engine.name": "ollama",
            "profiles.ollama.models.main": "qwen-del-perfil",
            "profiles.cerebras+ollama.models.main": "gemma-del-perfil",
        },
        {},
    )
    assert values["models.main"] == "qwen-del-perfil"
    assert sources["models.main"] == "file"


def test_switching_the_engine_in_the_file_switches_the_profile():
    file_values = {
        "engine.name": "cerebras+ollama",
        "profiles.ollama.models.main": "qwen-del-perfil",
        "profiles.cerebras+ollama.models.main": "gemma-del-perfil",
    }
    values, _ = store.resolve(SETTINGS, file_values, {})
    assert values["models.main"] == "gemma-del-perfil"


def test_a_silent_profile_falls_back_to_the_engine_default():
    values, sources = store.resolve(SETTINGS, {"engine.name": "cerebras+ollama"}, {})
    assert values["models.main"] == "gemma-4-31b"
    assert sources["models.main"] == "default"
    assert values["models.guardrail"] == "granite"


def test_a_pre_profile_top_level_value_still_resolves():
    values, sources = store.resolve(SETTINGS, {"models.main": "qwen-legado"}, {})
    assert values["models.main"] == "qwen-legado"
    assert sources["models.main"] == "file"


def test_the_profile_wins_over_a_legacy_top_level_value():
    values, _ = store.resolve(
        SETTINGS,
        {"models.main": "qwen-legado", "profiles.ollama.models.main": "qwen-del-perfil"},
        {},
    )
    assert values["models.main"] == "qwen-del-perfil"


def test_the_inactive_profile_keys_are_known_and_do_not_warn(caplog):
    store.resolve(
        SETTINGS,
        {"profiles.cerebras+ollama.models.main": "gemma-del-perfil"},
        {},
    )
    assert "desconocida" not in caplog.text


def test_write_file_places_scoped_values_under_the_given_profile(tmp_path):
    path = tmp_path / "config.json"
    store.write_file(
        path,
        SETTINGS,
        {"engine.name": "ollama", "engine.idle": 5},
        {"ollama": {"models.main": "qwen-x"}, "cerebras+ollama": {"models.main": "gemma-x"}},
    )
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["engine"]["idle"] == 5
    assert "models" not in written
    assert written["profiles"]["ollama"]["models"]["main"] == "qwen-x"
    assert written["profiles"]["cerebras+ollama"]["models"]["main"] == "gemma-x"


def test_profiles_round_trip_through_read_and_resolve(tmp_path):
    path = tmp_path / "config.json"
    store.write_file(
        path,
        SETTINGS,
        {"engine.name": "cerebras+ollama"},
        {"ollama": {"models.main": "qwen-x"}, "cerebras+ollama": {"models.main": "gemma-x"}},
    )
    values, _ = store.resolve(SETTINGS, store.read_file(path), {})
    assert values["models.main"] == "gemma-x"


@pytest.fixture
def sandbox(tmp_path):
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(store, "CONFIG_PATH", tmp_path / "config.json")
        vg_settings.load()
        yield tmp_path / "config.json"
    vg_settings.reload()


def test_update_writes_into_the_active_profile_and_preserves_the_other(sandbox):
    vg_settings.update({"models.main": "qwen-mio"})
    vg_settings.update({"engine.name": "cerebras+ollama"})
    assert vg_settings.values()["models.main"] == "gemma-4-31b"
    vg_settings.update({"models.main": "gemma-mio"})
    vg_settings.update({"engine.name": "ollama"})
    assert vg_settings.values()["models.main"] == "qwen-mio"
    written = json.loads(sandbox.read_text(encoding="utf-8"))
    assert written["profiles"]["ollama"]["models"]["main"] == "qwen-mio"
    assert written["profiles"]["cerebras+ollama"]["models"]["main"] == "gemma-mio"


def test_switching_engines_reports_the_impacts_of_the_swapped_values(sandbox):
    vg_settings.update({"models.main": "qwen-mio"})
    impacts = vg_settings.update({"engine.name": "cerebras+ollama"})
    assert vg_settings.Impact.ENGINE in impacts
    assert vg_settings.Impact.CONTEXTS in impacts


def test_reset_removes_the_key_from_the_active_profile_only(sandbox):
    vg_settings.update({"models.main": "qwen-mio"})
    vg_settings.update({"engine.name": "cerebras+ollama"})
    vg_settings.update({"models.main": "gemma-mio"})
    vg_settings.reset(["models.main"])
    assert vg_settings.values()["models.main"] == "gemma-4-31b"
    vg_settings.update({"engine.name": "ollama"})
    assert vg_settings.values()["models.main"] == "qwen-mio"


def test_the_snapshot_default_follows_the_active_engine(sandbox):
    vg_settings.update({"engine.name": "cerebras+ollama"})
    row = next(row for row in vg_settings.snapshot() if row["key"] == "models.main")
    assert row["default"] == "gemma-4-31b"
    assert row["scope"] == "engine"
