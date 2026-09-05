import pytest
from fastapi.testclient import TestClient

from server import installation
from server.app import app
from server.middleware import HSTS, csp


@pytest.fixture
def client(monkeypatch):
    # The checkout's own `.env` puts this process in production with a public base URL, so
    # without pinning the four answers the origin every assertion below turns on would be
    # whatever the machine running the suite is configured for.
    monkeypatch.setattr(installation, "public_base_url", lambda: None)
    monkeypatch.setattr(installation, "trust_proxy", lambda: False)
    monkeypatch.setattr(installation, "dev_cors_origins", lambda: [])
    monkeypatch.setattr(installation, "cookie_secure", lambda: False)
    return TestClient(app, raise_server_exceptions=False)


# THE ORDER OF THE TWO MIDDLEWARES -----------------------------------------------------------


# `add_middleware` inserts at the front, so the LAST one added is the outermost layer. With
# `SecurityHeaders` added first it sat INSIDE `OriginCheck`, and the 403 that `_refused()`
# builds never passed through it: the one response an attacker gets to look at went out with
# no `nosniff`, no CSP and no `X-Frame-Options`.
def test_a_refused_cross_site_request_still_carries_the_security_headers(client):
    response = client.post("/api/nada", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == csp()
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_the_403_is_the_origin_check_and_not_the_router(client):
    body = client.post("/api/nada", headers={"Origin": "https://evil.example"}).json()
    assert "origen" in body["detail"]


def test_a_same_origin_request_is_not_refused_and_is_covered_too(client):
    response = client.post("/api/nada", headers={"Origin": "http://testserver"})

    assert response.status_code != 403
    assert response.headers["x-content-type-options"] == "nosniff"


# THE POLICY ---------------------------------------------------------------------------------


def _connect_src(policy: str) -> list[str]:
    for directive in policy.split(";"):
        parts = directive.split()
        if parts and parts[0] == "connect-src":
            return parts[1:]
    raise AssertionError(f"«connect-src» no está en la política: {policy}")


# `ws:` and `wss:` are SCHEME sources: they match every host there is, so the directive that
# was meant to bound the socket bounded nothing. A `wss://host` is a different thing — it
# names one origin — and that distinction is the whole point, so the check is on the shape
# of each source and not on whether the string «wss» appears.
def test_no_source_is_a_bare_scheme(monkeypatch):
    monkeypatch.setattr(installation, "public_base_url", lambda: "https://variatio.example")
    sources = _connect_src(csp())

    assert "'self'" in sources
    for source in sources:
        assert not (source.endswith(":") and "//" not in source), f"esquema desnudo: {source}"


# Named beside `'self'`, not instead of it, and it is the installation's own host: it grants
# nothing new and rescues the browsers that predate CSP3's `'self'` matching a same-origin
# socket.
def test_the_declared_host_is_named_as_a_socket_origin(monkeypatch):
    monkeypatch.setattr(installation, "public_base_url", lambda: "https://variatio.example")
    assert _connect_src(csp()) == ["'self'", "wss://variatio.example"]


def test_without_a_declared_base_url_self_stands_alone(monkeypatch):
    monkeypatch.setattr(installation, "public_base_url", lambda: None)
    assert _connect_src(csp()) == ["'self'"]


def test_styles_keep_their_inline_allowance():
    assert "style-src 'self' 'unsafe-inline'" in csp()


# HSTS -----------------------------------------------------------------------------------------


def test_the_transport_header_is_sent_where_tls_terminates(client, monkeypatch):
    monkeypatch.setattr(installation, "cookie_secure", lambda: True)

    assert client.get("/api/nada").headers["strict-transport-security"] == HSTS


# `preload` is an entry compiled into every browser and unsetting the header does not undo
# it, so it is the user's commitment to make and not this file's.
def test_the_transport_header_asks_for_subdomains_and_not_for_preload():
    assert "includeSubDomains" in HSTS
    assert "preload" not in HSTS
    assert int(HSTS.split("max-age=")[1].split(";")[0]) >= 15_552_000


def test_local_http_development_is_never_pinned_to_https(client):
    assert "strict-transport-security" not in client.get("/api/nada").headers
