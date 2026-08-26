from server.routers import config as config_router
from variatio import config as vg_config
from variatio.core import cerebras, inference


def test_an_unreachable_engine_offers_no_models_and_no_error(monkeypatch):
    monkeypatch.setattr(inference, "is_available", lambda: False)
    assert config_router._models() == {"installed": [], "running": []}


def test_a_listing_failure_is_an_empty_list(monkeypatch):
    def boom():
        raise inference.InferenceError("sin motor")

    monkeypatch.setattr(inference, "is_available", lambda: True)
    monkeypatch.setattr(inference, "installed_models_detail", boom)
    monkeypatch.setattr(inference, "running_models", boom)
    assert config_router._models() == {"installed": [], "running": []}


def test_the_payload_carries_what_the_engine_has(monkeypatch):
    installed = [{"model": "qwen3.6:35b-a3b-q8_0", "size": 37_000_000_000}]
    running = [{"model": "qwen3-embedding:4b", "size_vram": 4_370_000_000}]
    monkeypatch.setattr(inference, "is_available", lambda: True)
    monkeypatch.setattr(inference, "installed_models_detail", lambda: installed)
    monkeypatch.setattr(inference, "running_models", lambda: running)
    payload = config_router._payload()
    assert payload["models"] == {"installed": installed, "running": running}
    assert {"groups", "settings"} <= set(payload)


def test_the_cerebras_catalog_needs_a_key(monkeypatch):
    monkeypatch.setattr(vg_config, "CEREBRAS_API_KEY", "")
    monkeypatch.setattr(vg_config, "CEREBRAS_MODELS", ["gemma-4-31b"])
    out = config_router.cerebras_models()
    assert out["source"] == "config"
    assert out["models"] == ["gemma-4-31b"]
    assert "CEREBRAS_API_KEY" in out["error"]


def test_the_cerebras_catalog_comes_from_the_api_when_there_is_a_key(monkeypatch):
    monkeypatch.setattr(vg_config, "CEREBRAS_API_KEY", "sk-prueba")
    monkeypatch.setattr(cerebras, "catalog", lambda: ["gemma-4-31b", "qwen-3-235b"])
    out = config_router.cerebras_models()
    assert out == {"models": ["gemma-4-31b", "qwen-3-235b"], "source": "api", "error": None}


def test_an_unreachable_cerebras_falls_back_to_the_declared_routing(monkeypatch):
    def boom():
        raise inference.InferenceError("sin red")

    monkeypatch.setattr(vg_config, "CEREBRAS_API_KEY", "sk-prueba")
    monkeypatch.setattr(vg_config, "CEREBRAS_MODELS", ["gemma-4-31b"])
    monkeypatch.setattr(cerebras, "catalog", boom)
    out = config_router.cerebras_models()
    assert out["source"] == "config"
    assert out["models"] == ["gemma-4-31b"]
    assert "sin red" in out["error"]
