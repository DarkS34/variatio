import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import settings
from server.routers import ws as ws_module


# `OriginCheck` is a `BaseHTTPMiddleware`, which hands every non-`http` scope straight on, so
# `/ws` never reached it. Nothing was exploitable while the session cookie is `SameSite=Lax`
# — a browser does not attach a Lax cookie to a cross-site handshake — but the HTTP path
# deliberately refuses to rely on that, and the socket was the one place that did.
@pytest.fixture
def attempts(monkeypatch):
    """Every socket that got as far as being asked for a session."""
    seen: list = []
    monkeypatch.setattr(ws_module, "authenticate_socket", lambda socket: seen.append(socket))
    return seen


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", lambda: None)
    monkeypatch.setattr(settings, "trust_proxy", lambda: False)
    monkeypatch.setattr(settings, "dev_cors_origins", lambda: [])
    app = FastAPI()
    app.include_router(ws_module.router)
    return TestClient(app)


# A refusal is an `accept()` followed at once by close 4401, because a close code only
# travels on an established connection — see `test_ws_refusal.py`. So the handshake itself
# succeeds and the verdict arrives as the first message.
def _refusal(client, headers=None) -> int:
    with client.websocket_connect("/ws", headers=headers or {}) as socket:
        message = socket.receive()
    assert message["type"] == "websocket.close"
    return message["code"]


def test_a_handshake_from_another_origin_is_closed_before_the_cookie_is_read(client, attempts):
    assert _refusal(client, {"Origin": "https://evil.example"}) == ws_module.UNAUTHORISED
    assert attempts == []


def test_a_fetch_metadata_header_that_says_cross_site_is_enough(client, attempts):
    assert _refusal(client, {"Sec-Fetch-Site": "cross-site"}) == ws_module.UNAUTHORISED
    assert attempts == []


# The socket the app itself opens: `runStore.connect()` builds the URL from
# `window.location.host`, so its `Origin` is always the page's own.
def test_the_app_own_socket_still_reaches_the_session_check(client, attempts):
    assert _refusal(client, {"Origin": "http://testserver"}) == ws_module.UNAUTHORISED
    assert len(attempts) == 1


# The deliberate allowance the HTTP path already makes: a request with no `Origin` at all is
# a script or a CLI, which cannot be the browser a cross-site attack needs.
def test_a_client_that_sends_no_origin_connects_as_it_always_did(client, attempts):
    assert _refusal(client) == ws_module.UNAUTHORISED
    assert len(attempts) == 1
