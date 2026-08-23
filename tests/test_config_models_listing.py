from server.routers import config as config_router
from variant_generator.core import inference


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
