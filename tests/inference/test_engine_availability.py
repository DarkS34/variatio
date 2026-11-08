import httpx
import pytest

from variatio import inference
from variatio.settings import engine_profile


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("timed out"),
        httpx.ConnectTimeout("timed out"),
        httpx.ConnectError("refused"),
        httpx.PoolTimeout("no connection"),
        httpx.RemoteProtocolError("bad response"),
    ],
)
def test_every_transport_failure_reads_as_unavailable(monkeypatch, failure):
    def boom(*args, **kwargs):
        raise failure

    monkeypatch.setattr(httpx, "get", boom)
    assert inference.engine().is_available() is False


def test_a_non_200_reads_as_unavailable(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: httpx.Response(503, request=httpx.Request("GET", "http://x"))
    )
    assert inference.engine().is_available() is False


def test_a_200_reads_as_available(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: httpx.Response(200, request=httpx.Request("GET", "http://x"))
    )
    assert inference.engine().is_available() is True


def test_required_models_resolves_the_phase_registry():
    required = inference.required_models()
    assert engine_profile().KG_EXTRACT_MODEL in required.values()
    assert engine_profile().EMBEDDING_LLM in required.values()
