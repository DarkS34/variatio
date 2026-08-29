import asyncio

import pytest
from fastapi import FastAPI

from server import settings
from server.routers import ws as ws_module


# WHY THIS FILE EXISTS BESIDE `test_ws_origin.py`, WHICH ALREADY ASSERTS THE 4401.
#
# Starlette's `TestClient` hands the close code to the client whether or not the socket was
# ever accepted, so every refusal test passed while no browser ever saw the code: under
# uvicorn, closing before `accept()` answers the handshake with HTTP 403 and the browser
# synthesises a bare 1006. Measured in Chromium against the running app:
# `{"code": 1006, "reason": "", "wasClean": false}`.
#
# What the client does with that is the whole point — `runStore` treats anything but 4401 as
# a network hiccup and reconnects, so a rejected cookie produced an endless loop instead of
# sending anyone back to the login. The invariant is therefore about the ORDER of the two
# ASGI messages, which is the one thing `TestClient` cannot show.


class _Socket:
    def __init__(self) -> None:
        self.calls: list = []

    async def accept(self) -> None:
        self.calls.append("accept")

    async def close(self, code: int | None = None) -> None:
        self.calls.append(("close", code))


def test_a_refusal_accepts_before_it_closes():
    socket = _Socket()
    asyncio.run(ws_module.refuse(socket))
    assert socket.calls == ["accept", ("close", ws_module.UNAUTHORISED)]


def _scope(headers: dict[str, str]) -> dict:
    return {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": "/ws",
        "raw_path": b"/ws",
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "subprotocols": [],
        "state": {},
    }


def _messages(app, headers: dict[str, str]) -> list[dict]:
    sent: list[dict] = []
    incoming = [{"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1005}]

    async def receive():
        return incoming.pop(0) if incoming else {"type": "websocket.disconnect", "code": 1005}

    async def send(message):
        sent.append(message)

    asyncio.run(app(_scope(headers), receive, send))
    return sent


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", lambda: None)
    monkeypatch.setattr(settings, "trust_proxy", lambda: False)
    monkeypatch.setattr(settings, "dev_cors_origins", lambda: [])
    monkeypatch.setattr(ws_module, "authenticate_socket", lambda socket: None)
    application = FastAPI()
    application.include_router(ws_module.router)
    return application


def test_a_socket_with_no_session_is_accepted_and_then_closed_with_4401(app):
    sent = _messages(app, {"Origin": "http://testserver"})

    assert [message["type"] for message in sent] == ["websocket.accept", "websocket.close"]
    assert sent[-1]["code"] == ws_module.UNAUTHORISED


def test_a_cross_site_handshake_is_refused_the_same_way(app):
    sent = _messages(app, {"Origin": "https://evil.example"})

    assert [message["type"] for message in sent] == ["websocket.accept", "websocket.close"]
    assert sent[-1]["code"] == ws_module.UNAUTHORISED
