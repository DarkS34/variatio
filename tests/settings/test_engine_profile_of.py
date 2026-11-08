"""Each engine reads its own profile, and every engine reads the local models from `ollama`'s."""

import contextvars

import pytest

from variatio import settings as vg_settings
from variatio.settings import SettingError, store


@pytest.fixture
def sandbox(tmp_path):
    path = tmp_path / "config.json"
    store.write_file(
        path,
        list(vg_settings.REGISTRY),
        {"engine.name": "ollama"},
        {
            "ollama": {"models.guardrail": "guarda-local", "models.phases.kg_extract": "qwen-mio"},
            "cerebras+ollama": {
                "models.guardrail": "guarda-del-hibrido",
                "models.phases.kg_extract": "gemma-mio",
            },
        },
    )
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(store, "CONFIG_PATH", path)
        vg_settings.load()
        yield path
    vg_settings.reload()


def test_each_engine_reads_its_own_phase_models(sandbox):
    assert vg_settings.profile_of("ollama").KG_EXTRACT_MODEL == "qwen-mio"
    assert vg_settings.profile_of("cerebras+ollama").KG_EXTRACT_MODEL == "gemma-mio"


def test_every_engine_reads_the_guardrail_from_the_ollama_profile(sandbox):
    assert vg_settings.profile_of("cerebras+ollama").GUARDRAIL_LLM == "guarda-local"


def test_a_profile_holds_no_installation_setting(sandbox):
    with pytest.raises(AttributeError):
        vg_settings.profile_of("ollama").OLLAMA_HOST


def test_with_no_engine_fixed_the_profile_raises():
    with pytest.raises(SettingError, match="No hay perfil"):
        contextvars.Context().run(vg_settings.engine_profile)


def test_the_panel_writes_the_guardrail_window_into_the_ollama_profile(sandbox):
    vg_settings.update({"engine.name": "cerebras+ollama"})
    vg_settings.update({"context_window.guardrail": 2048})
    assert vg_settings.values()["context_window.guardrail"] == 2048
    for engine in ("ollama", "cerebras+ollama"):
        assert vg_settings.profile_of(engine).LLM_CONTEXT["guarda-local"] == 2048
