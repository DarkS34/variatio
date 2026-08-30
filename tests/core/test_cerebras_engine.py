import json

import httpx
import pytest

from variatio import config
from variatio.core import cerebras, cerebras_budget, progress
from variatio.core.cerebras import CerebrasEngine, HybridEngine
from variatio.core.inference import InferenceError


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


def test_strict_schema_drops_the_titles_pydantic_writes():
    schema = {
        "type": "object",
        "title": "ContentItem",
        "properties": {
            "enunciado": {"type": "string", "title": "Enunciado"},
            "title": {"type": "string", "title": "Title"},
        },
    }
    adapted = cerebras.strict_schema(schema)
    assert "title" not in adapted
    assert set(adapted["properties"]) == {"enunciado", "title"}
    assert "title" not in adapted["properties"]["enunciado"]


def test_strict_schema_rewrites_const_as_a_single_enum():
    schema = {
        "type": "object",
        "properties": {"item_type": {"const": "problema_formal"}},
        "required": ["item_type"],
    }
    adapted = cerebras.strict_schema(schema)
    assert adapted["properties"]["item_type"] == {"enum": ["problema_formal"]}


def test_a_root_array_is_wrapped_and_keeps_strict():
    schema = {"type": "array", "items": {"type": "object", "properties": {"a": {"type": "string"}}}}
    shaped = cerebras.response_format(schema)
    assert shaped["json_schema"]["strict"] is True
    assert shaped["json_schema"]["name"] == cerebras._WRAPPER_NAME
    wrapper = shaped["json_schema"]["schema"]
    assert wrapper["type"] == "object"
    assert wrapper["required"] == ["items"]
    assert wrapper["properties"]["items"]["type"] == "array"
    assert wrapper["properties"]["items"]["items"]["additionalProperties"] is False


def test_a_root_array_too_big_to_wrap_loses_strict_but_not_the_shape():
    campos = {f"campo_{i}": {"type": "string"} for i in range(400)}
    schema = {"type": "array", "items": {"type": "object", "properties": campos}}
    cerebras._WARNED.clear()
    try:
        shaped = cerebras.response_format(schema)
    finally:
        cerebras._WARNED.clear()
    assert shaped["json_schema"]["strict"] is False
    assert shaped["json_schema"]["name"] == "respuesta"
    assert shaped["json_schema"]["schema"]["type"] == "array"


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


def test_an_oversized_schema_is_reported_once_per_schema():
    from loguru import logger

    said: list[str] = []
    cerebras._WARNED.clear()
    sink = logger.add(lambda m: said.append(m.record["message"]), level="WARNING")
    try:
        campos = {f"campo_{i}": {"type": "string"} for i in range(400)}
        otros = {f"otro_{i}": {"type": "string"} for i in range(400)}
        huge = {"type": "object", "properties": campos}
        other = {"type": "object", "properties": otros}
        cerebras.response_format(huge)
        cerebras.response_format(huge)
        cerebras.response_format(other)
    finally:
        logger.remove(sink)
        cerebras._WARNED.clear()

    assert len([m for m in said if "The schema measures" in m]) == 2


def test_an_oversized_schema_loses_strict_but_not_the_shape():
    huge = {
        "type": "object",
        "properties": {f"campo_{i}": {"type": "string"} for i in range(400)},
    }
    shaped = cerebras.response_format(huge)
    assert shaped["json_schema"]["strict"] is False


def test_reasoning_effort_speaks_cerebras():
    assert cerebras.reasoning_effort(None) is None
    assert cerebras.reasoning_effort(False) == "none"
    assert cerebras.reasoning_effort(True) == "low"


def test_a_per_phase_effort_travels_as_itself():
    assert cerebras.reasoning_effort("medium") == "medium"
    assert cerebras.reasoning_effort("max") == "high"


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
    assert hybrid._backend("qwen3.8:27b-q8_0") is hybrid._ollama
    assert hybrid.remote_models() == frozenset({"gemma-4-31b"})


def test_a_remote_model_cannot_embed(hybrid):
    with pytest.raises(InferenceError, match="embedding"):
        hybrid.embed("gemma-4-31b", "texto")


def test_a_remote_model_cannot_be_pulled_or_deleted(hybrid):
    with pytest.raises(InferenceError, match="descargar"):
        hybrid.pull("gemma-4-31b")
    with pytest.raises(InferenceError, match="borrar"):
        hybrid.delete("gemma-4-31b")


def test_a_remote_model_unloads_as_a_no_op(hybrid):
    assert hybrid.unload("gemma-4-31b") is True


def test_the_remote_capabilities_are_declared_not_asked(hybrid):
    assert hybrid.supports_thinking("gemma-4-31b") is True
    assert hybrid.supports_vision("gemma-4-31b") is True
    assert hybrid._cerebras.supports_vision("otro-modelo-31b") is False


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


def test_generate_unwraps_the_reply_to_a_wrapped_array_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        assert sent["response_format"]["json_schema"]["name"] == cerebras._WRAPPER_NAME
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"items": [{"a": "x"}]}'}}]},
        )

    engine = _engine_with(handler)
    schema = {"type": "array", "items": {"type": "object", "properties": {"a": {"type": "string"}}}}
    resp = engine.generate("gemma-4-31b", "hola", format=schema)
    assert json.loads(resp.response) == [{"a": "x"}]


def test_an_unwrappable_reply_travels_as_it_arrived():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "[1, 2]"}}]})

    engine = _engine_with(handler)
    schema = {"type": "array", "items": {"type": "integer"}}
    resp = engine.generate("gemma-4-31b", "hola", format=schema)
    assert resp.response == "[1, 2]"


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


def test_a_readable_error_names_the_status_and_the_endpoint_but_not_the_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="reasoning_effort is not supported")

    with pytest.raises(InferenceError, match="400.*chat/completions") as error:
        _engine_with(handler).generate("gemma-4-31b", "hola")
    assert "reasoning_effort is not supported" not in str(error.value)


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


# THE THROTTLE IS WIRED INTO THE ENGINE ----------------------------------------------------
#
# The ledger's own arithmetic is pinned in `test_cerebras_budget.py`; what these check is
# the wiring, which is the part that silently does nothing if a call site is missed.


def test_a_call_is_charged_to_the_ledger_with_its_usage_and_phase(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hola"}}],
                "usage": {"prompt_tokens": 640, "completion_tokens": 60},
            },
            headers={"x-ratelimit-remaining-requests-minute": "4"},
        )

    with progress.step("kg_extract", "Extrayendo"):
        _engine_with(handler).generate("gemma-4-31b", "texto")

    entry = cerebras_budget.shared().snapshot()["models"][0]
    assert entry["model"] == "gemma-4-31b"
    assert entry["windows"]["minute"]["requests_used"] == 1
    assert entry["phases"] == [
        {
            "phase": "kg_extract",
            "requests": 1,
            "prompt_tokens": 640,
            "completion_tokens": 60,
            "tokens": 700,
        }
    ]


# A 429 spent a request whether or not it produced an answer. A ledger that only counted
# successes would walk straight back into the limit it had just hit.
def test_a_refused_call_is_charged_too(monkeypatch):
    monkeypatch.setattr(cerebras, "_MAX_ATTEMPTS", 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "slow down"})

    with pytest.raises(InferenceError):
        _engine_with(handler).generate("gemma-4-31b", "texto")

    assert cerebras_budget.shared().snapshot()["models"][0]["windows"]["day"]["requests_used"] == 1


def test_the_engine_holds_the_call_until_the_window_has_room(monkeypatch):
    held: list[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(
        cerebras_budget.Budget, "wait", lambda self, model, tokens, phase=None: held.append((model, tokens))
    )
    _engine_with(handler).generate("gemma-4-31b", "x" * 4_000)

    assert len(held) == 1
    assert held[0][0] == "gemma-4-31b"
    # Sized from the prompt before it goes out; `record` replaces it with the exact usage.
    assert held[0][1] > 900


def test_an_exhausted_day_stops_the_call_from_leaving(monkeypatch):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    # A ceiling the call would fit under, already spent: that is «agotado». A ceiling
    # SMALLER than the call is the other refusal, «no cabe», pinned in the budget's tests.
    monkeypatch.setattr(config, "CEREBRAS_MAX_TOKENS_DAY", 2_000)
    cerebras_budget.shared().record(
        "gemma-4-31b", "kg_extract", prompt_tokens=1_900, completion_tokens=0, headers={}
    )

    with pytest.raises(cerebras_budget.BudgetExhausted, match="agotado"):
        _engine_with(handler).generate("gemma-4-31b", "x" * 4_000)

    assert sent == []


def test_a_streamed_call_asks_for_its_usage():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        body = (
            'data: {"choices":[{"delta":{"content":"hola"}}]}\n'
            'data: {"choices":[],"usage":{"prompt_tokens":90,"completion_tokens":10}}\n'
            "data: [DONE]\n"
        )
        return httpx.Response(200, text=body)

    _engine_with(handler).generate_stream("gemma-4-31b", "texto", on_token=lambda text, channel: None)

    # Without `include_usage` a streamed answer carries none, and the generator — the one
    # call of the pipeline that streams — would be charged zero tokens.
    assert seen["stream_options"] == {"include_usage": True}
    assert cerebras_budget.shared().snapshot()["models"][0]["phases"][0]["tokens"] == 100
