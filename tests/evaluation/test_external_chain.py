"""The commercial arm's chain: who is tried, in what order, and who is recorded."""

import httpx
import pytest

from evaluation import ArmUnavailable
from evaluation.arms import external


def _http_error(status: int) -> httpx.HTTPStatusError:
    """Build the failure a real provider raises when its free quota is spent."""
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    return httpx.HTTPStatusError(
        f"{status}", request=request, response=httpx.Response(status, request=request)
    )


@pytest.fixture
def chain(monkeypatch):
    """Drive `generate` over a chain of fakes, with no settings and no network."""

    def install(providers: list[str], callers: dict):
        monkeypatch.setattr(external, "configured_providers", lambda: providers)
        monkeypatch.setattr(external, "_model", lambda p: f"{p}-model")
        monkeypatch.setattr(external, "_key", lambda p: f"{p}-key")
        monkeypatch.setattr(external, "_CALLERS", callers)

    return install


def test_a_spent_quota_hands_over_to_the_next_provider(chain):
    def spent(prompt, model, key):
        raise _http_error(429)

    chain(["gemini", "mistral"], {"gemini": spent, "mistral": lambda *_: "el ítem"})
    answer = external.generate("enunciado")
    assert (answer.text, answer.provider, answer.model) == (
        "el ítem",
        "mistral",
        "mistral-model",
    )


def test_the_session_is_filed_under_whoever_answered(chain):
    """Never under the head of the chain: a fallback that lies is a corrupted measurement."""

    def spent(prompt, model, key):
        raise _http_error(429)

    chain(["gemini", "mistral", "groq"], {"gemini": spent, "mistral": spent, "groq": lambda *_: "x"})
    assert external.generate("enunciado").provider == "groq"


def test_nobody_answering_raises_with_every_reason(chain):
    def refused(prompt, model, key):
        raise _http_error(401)

    chain(["gemini", "mistral"], {"gemini": refused, "mistral": refused})
    with pytest.raises(ArmUnavailable) as failure:
        external.generate("enunciado")
    assert "gemini" in str(failure.value) and "mistral" in str(failure.value)


def test_mistral_is_a_callable_link_of_the_chain():
    assert list(external._CALLERS) == ["gemini", "mistral", "groq"]


def test_mistral_speaks_the_openai_shape_with_no_grammar(monkeypatch):
    """No `response_format` goes out here either — the baseline asks in prose or not at all."""
    sent = {}

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent.update(kwargs)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": "el ítem"}}]},
        )

    monkeypatch.setattr(external.httpx, "post", fake_post)
    assert external._mistral("enunciado", "mistral-medium-latest", "clave") == "el ítem"
    assert sent["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer clave"
    assert sent["json"]["model"] == "mistral-medium-latest"
    assert "response_format" not in sent["json"]
