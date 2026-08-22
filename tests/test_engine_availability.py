import httpx
import pytest

from variant_generator.core import inference


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
