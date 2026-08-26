import json

import httpx
import pytest

from variant_generator import config
from variant_generator.core import cerebras
from variant_generator.core.cerebras import CerebrasEngine, HybridEngine
from variant_generator.core.inference import InferenceError


def test_strict_schema_closes_every_object():
    schema = {
        "type": "object",
        "properties": {
            "concepts": {
                "type": "array",
                "items": {"type": "object", "properties": {"name": {"type": "string"}}},
            }
        },
        "required": ["concepts"],
    }
    adapted = cerebras.strict_schema(schema)
    assert adapted["additionalProperties"] is False
    assert adapted["properties"]["concepts"]["items"]["additionalProperties"] is False


def test_strict_schema_drops_what_strict_mode_refuses():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "pattern": "^[a-z]+$", "maxLength": 10},
            "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        },
    }
    adapted = cerebras.strict_schema(schema)
    assert "pattern" not in adapted["properties"]["name"]
    assert "maxLength" not in adapted["properties"]["name"]
    assert "minItems" not in adapted["properties"]["tags"]
    assert "maxItems" not in adapted["properties"]["tags"]


def test_strict_schema_keeps_a_property_named_like_a_keyword():
    schema = {
        "type": "object",
        "properties": {"format": {"type": "string"}, "pattern": {"type": "string"}},
    }
    adapted = cerebras.strict_schema(schema)
    assert set(adapted["properties"]) == {"format", "pattern"}


def test_response_format_maps_the_three_shapes():
    assert cerebras.response_format(None) is None
    assert cerebras.response_format("json") == {"type": "json_object"}
    shaped = cerebras.response_format({"type": "object", "properties": {}})
    assert shaped["type"] == "json_schema"
    assert shaped["json_schema"]["strict"] is True


def test_strict_schema_keeps_an_open_map_typed():
    schema = {
        "type": "object",
        "properties": {
            "domains": {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
            }
        },
        "required": ["domains"],
    }
    adapted = cerebras.strict_schema(schema)
    assert adapted["additionalProperties"] is False
    assert adapted["properties"]["domains"]["additionalProperties"] == {
        "type": "array",
        "items": {"type": "string"},
    }


def test_an_open_map_loses_strict_but_not_the_shape():
    schema = {
        "type": "object",
        "properties": {"drop": {"type": "object", "additionalProperties": {"type": "string"}}},
        "required": ["drop"],
    }
    shaped = cerebras.response_format(schema)
    assert shaped["json_schema"]["strict"] is False
    assert shaped["json_schema"]["schema"]["properties"]["drop"]["additionalProperties"] == {
        "type": "string"
    }


def test_an_oversized_schema_loses_strict_but_not_the_shape():
    huge = {
        "type": "object",
        "properties": {f"campo_{i}": {"type": "string"} for i in range(400)},
    }
    shaped = cerebras.response_format(huge)
    assert shaped["json_schema"]["strict"] is False


def test_reasoning_effort_speaks_cerebras():
    assert cerebras.reasoning_effort(None, "gemma-4-31b") is None
    assert cerebras.reasoning_effort(False, "gemma-4-31b") == "none"
    assert cerebras.reasoning_effort(True, "gemma-4-31b") == "low"


def test_think_false_floors_at_low_where_reasoning_has_no_off_switch():
    assert cerebras.reasoning_effort(False, "gpt-oss-120b") == "low"


def test_a_per_phase_effort_travels_as_itself():
    assert cerebras.reasoning_effort("medium", "gemma-4-31b") == "medium"
    assert cerebras.reasoning_effort("max", "gemma-4-31b") == "high"


def test_the_shared_catalog_reuses_one_engine_per_base_url(monkeypatch):
    built = []

    class Fake:
        def __init__(self):
            built.append(self)

        def catalog(self):
            return ["gemma-4-31b"]

    monkeypatch.setattr(cerebras, "CerebrasEngine", Fake)
    monkeypatch.setattr(cerebras, "_shared", None)
    monkeypatch.setattr(cerebras, "_shared_base", None)
    monkeypatch.setattr(config, "CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    assert cerebras.catalog() == ["gemma-4-31b"]
    assert cerebras.catalog() == ["gemma-4-31b"]
    assert len(built) == 1
    monkeypatch.setattr(config, "CEREBRAS_BASE_URL", "http://localhost:9999/v1")
    cerebras.catalog()
    assert len(built) == 2


@pytest.fixture
def hybrid(monkeypatch):
    monkeypatch.setattr(config, "CEREBRAS_MODELS", ["gemma-4-31b"])
    return HybridEngine()


def test_the_hybrid_routes_by_membership(hybrid):
    assert hybrid._backend("gemma-4-31b") is hybrid._cerebras
    assert hybrid._backend("qwen3.8:27b-q4_K_M") is hybrid._ollama
    assert hybrid.remote_models() == frozenset({"gemma-4-31b"})


def test_a_remote_model_cannot_embed(hybrid):
    with pytest.raises(InferenceError, match="embedding"):
        hybrid.embed("gemma-4-31b", "texto")


def test_a_remote_model_cannot_be_pulled_or_deleted(hybrid):
    with pytest.raises(InferenceError, match="descargar"):
        hybrid.pull("gemma-4-31b")
    with pytest.raises(InferenceError, match="borrar"):
        hybrid.delete("gemma-4-31b")


def test_a_remote_model_warms_and_unloads_as_a_no_op(hybrid):
    assert hybrid.warmup("gemma-4-31b") is None
    assert hybrid.unload("gemma-4-31b") is True


def test_the_remote_capabilities_are_declared_not_asked(hybrid):
    assert hybrid.supports_thinking("gemma-4-31b") is True
    assert hybrid.supports_vision("gemma-4-31b") is True
    assert hybrid._cerebras.supports_vision("gpt-oss-120b") is False


def _engine_with(handler) -> CerebrasEngine:
    engine = CerebrasEngine()
    engine._client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.cerebras.ai/v1"
    )
    return engine


def test_generate_sends_the_translated_call_and_splits_the_reasoning():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"ok": true}', "reasoning": "pensando…"}}
                ]
            },
        )

    engine = _engine_with(handler)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    resp = engine.generate("gemma-4-31b", "hola", think=True, temperature=0.2, format=schema)
    assert seen["model"] == "gemma-4-31b"
    assert seen["reasoning_effort"] == "low"
    assert seen["temperature"] == 0.2
    assert seen["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert seen["messages"][-1] == {"role": "user", "content": "hola"}
    assert resp.response == '{"ok": true}'
    assert resp.thinking == "pensando…"


def test_think_false_travels_as_none_which_is_gemmas_default_off(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    _engine_with(handler).generate("gemma-4-31b", "hola", think=False)
    assert seen["reasoning_effort"] == "none"


def test_a_429_is_retried_with_the_wait_the_server_asks_for(monkeypatch):
    monkeypatch.setattr(cerebras.time, "sleep", lambda seconds: None)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"retry-after": "1"}, text="rate limit")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    resp = _engine_with(handler).generate("gemma-4-31b", "hola")
    assert calls["count"] == 2
    assert resp.response == "ok"


def test_a_readable_error_names_the_status_and_the_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="reasoning_effort is not supported")

    with pytest.raises(InferenceError, match="400.*reasoning_effort"):
        _engine_with(handler).generate("gemma-4-31b", "hola")


def test_generate_stream_splits_the_two_channels():
    lines = [
        'data: {"choices": [{"delta": {"reasoning": "pienso"}}]}',
        'data: {"choices": [{"delta": {"content": "res"}}]}',
        'data: {"choices": [{"delta": {"content": "puesta"}}]}',
        "data: [DONE]",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="\n".join(lines))

    tokens: list[tuple[str, str]] = []
    resp = _engine_with(handler).generate_stream(
        "gemma-4-31b", "hola", think=True, on_token=lambda text, channel: tokens.append((channel, text))
    )
    assert resp.response == "respuesta"
    assert resp.thinking == "pienso"
    assert ("thinking", "pienso") in tokens
    assert ("answer", "res") in tokens
