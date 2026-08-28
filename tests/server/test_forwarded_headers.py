import pytest
from loguru import logger
from starlette.requests import Request

from server import settings
from server.auth import deps

PEER = "198.51.100.4"


def _request(headers: dict[str, str] | None = None, peer: str | None = PEER) -> Request:
    raw = {"host": "api.interna"} | (headers or {})
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in raw.items()],
            "client": (peer, 1234) if peer else None,
            "scheme": "http",
            "server": ("api.interna", 8000),
            "query_string": b"",
        }
    )


@pytest.fixture
def behind_a_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy", lambda: True)


# WHO IS ASKING ---------------------------------------------------------------------------


def test_with_no_forwarded_header_the_socket_peer_is_the_client(behind_a_proxy):
    assert deps.client_ip(_request()) == PEER


def test_a_single_entry_is_what_the_proxy_wrote(behind_a_proxy):
    assert deps.client_ip(_request({"x-forwarded-for": "203.0.113.7"})) == "203.0.113.7"


def test_the_last_entry_of_a_chain_wins_because_it_is_the_one_the_proxy_appended(
    behind_a_proxy,
):
    forwarded = "1.1.1.1, 2.2.2.2, 203.0.113.7"
    assert deps.client_ip(_request({"x-forwarded-for": forwarded})) == "203.0.113.7"


def test_spaces_and_empty_entries_never_become_the_key(behind_a_proxy):
    forwarded = " 1.1.1.1 , ,  203.0.113.7 ,"
    assert deps.client_ip(_request({"x-forwarded-for": forwarded})) == "203.0.113.7"


def test_without_a_proxy_to_trust_the_header_is_not_read(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy", lambda: False)
    assert deps.client_ip(_request({"x-forwarded-for": "203.0.113.7"})) == PEER


def test_a_request_with_no_client_at_all_has_no_key(behind_a_proxy):
    assert deps.client_ip(_request(peer=None)) == ""


# WHERE A LINK POINTS ---------------------------------------------------------------------


def test_the_configured_address_is_the_one_the_links_carry(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", lambda: "https://variatio.example")
    asked = _request({"origin": "https://malo.example"})
    assert deps.base_url(asked) == "https://variatio.example"


def test_the_origin_of_whoever_asked_is_never_reflected_into_a_link(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", lambda: None)
    monkeypatch.setattr(settings, "is_production", lambda: False)
    asked = _request({"origin": "https://malo.example"})
    assert deps.base_url(asked) == "http://api.interna"


def test_an_installation_in_production_without_the_variable_says_so_once(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", lambda: None)
    monkeypatch.setattr(settings, "is_production", lambda: True)
    monkeypatch.setattr(deps, "_UNCONFIGURED_BASE_URL_REPORTED", False)

    said: list[str] = []
    sink = logger.add(said.append, level="WARNING")
    try:
        deps.base_url(_request())
        deps.base_url(_request())
    finally:
        logger.remove(sink)

    assert len(said) == 1
    assert "PUBLIC_BASE_URL" in said[0]


def test_and_in_development_it_says_nothing(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", lambda: None)
    monkeypatch.setattr(settings, "is_production", lambda: False)
    monkeypatch.setattr(deps, "_UNCONFIGURED_BASE_URL_REPORTED", False)

    said: list[str] = []
    sink = logger.add(said.append, level="WARNING")
    try:
        deps.base_url(_request())
    finally:
        logger.remove(sink)

    assert said == []
