"""The two things a cookie-authenticated app needs in front of every request.

Once the session lives in a cookie the browser attaches it to *any* request it makes,
including one a page on another site caused. Same-origin plus `SameSite=Lax` already
stops most of it; checking the origin of every state-changing request is the part that
does not depend on the browser being recent.
"""

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from . import settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# `frame-ancestors` and `X-Frame-Options` say the same thing to two generations of
# browser. `unsafe-inline` survives only for styles: React writes element `style`
# attributes (the graph canvas among them) and CSP has no nonce for those.
#
# `connect-src` is `'self'` and NOTHING ELSE. It used to read `'self' ws: wss:`, and those
# two are scheme sources: they match every host there is, so the directive placed no
# restriction at all on where an injected script could open a socket. In CSP3 `'self'`
# already covers a same-origin `ws:`/`wss:`, which is the only socket this app opens —
# `runStore.connect()` builds the URL from `window.location.host`. Re-adding a bare scheme
# to make some client work would give back the exfiltration channel, not fix a bug.
# The socket's own origin is named beside `'self'` when the installation declares one. It
# grants nothing `'self'` does not already cover — same host, same port — and exists for the
# browsers that predate CSP3's rule that `'self'` matches a same-origin `wss:` (Safari below
# 16). Without a `PUBLIC_BASE_URL` there is nothing to name and `'self'` stands alone.
def _socket_origin() -> str:
    base = settings.public_base_url()
    if not base:
        return ""
    split = urlsplit(base)
    if not split.hostname:
        return ""
    scheme = "wss" if split.scheme == "https" else "ws"
    return f" {scheme}://{split.netloc}"


def csp() -> str:
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        f"connect-src 'self'{_socket_origin()}; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )


HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}

# Six months, which is the shortest max-age anybody counts as a real commitment, and
# `includeSubDomains` because the session cookie is not host-only. NO `preload`: that one
# is an entry in a list compiled into every browser and is not undone by unsetting the
# header, so it is the user's decision and not this file's.
#
# Sent only where TLS actually terminates in front of us — `cookie_secure()` is the
# existing answer to that question, and it is the same fact: over plain http a browser
# ignores HSTS anyway, and in development it would pin localhost to https for six months.
# This header belongs at the proxy; it is here because the deployment's Caddy adds none.
HSTS = "max-age=15552000; includeSubDomains"


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for header, value in HEADERS.items():
            response.headers.setdefault(header, value)
        response.headers.setdefault("Content-Security-Policy", csp())
        if settings.cookie_secure():
            response.headers.setdefault("Strict-Transport-Security", HSTS)
        return response


# The rule is "reject on positive evidence of cross-site", not "require proof of
# same-site": a request with neither header is a script or a CLI, which cannot be a CSRF
# vector — the attack needs a browser, and every browser sends at least one of the two.
class OriginCheck(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request, call_next):
        if request.method in SAFE_METHODS:
            return await call_next(request)
        if cross_site(request):
            return _refused()
        return await call_next(request)


# The same verdict for an HTTP request and for a WebSocket handshake, which is why it takes
# an `HTTPConnection` and not a `Request`: `BaseHTTPMiddleware` short-circuits every scope
# that is not `http`, so `/ws` never reaches `OriginCheck` and had to ask for itself. One
# reading of "same site" and not two — a second copy is how the socket ends up with a rule
# the HTTP path has already outgrown.
def cross_site(connection) -> bool:
    fetch_site = connection.headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in ("same-origin", "none"):
        return True
    origin = connection.headers.get("origin")
    return bool(origin and origin not in _allowed(connection))


# A handshake arrives as `ws://`/`wss://` while the browser's `Origin` is always the page's
# `http://`/`https://`, so comparing the two literally refuses every socket.
_PAGE_SCHEME = {"ws": "http", "wss": "https"}


def _allowed(connection) -> set[str]:
    # With `PUBLIC_BASE_URL` set, that IS the origin the app is served under, and nothing
    # is derived from the request any more. What that removes is `X-Forwarded-Host`:
    # `trust_proxy()` defaults to on in production, so anyone able to send both
    # `Origin: https://evil.com` and `X-Forwarded-Host: evil.com` used to have their own
    # origin added to this set and passed the check. Not browser-driven — neither header is
    # CORS-safelisted — but the header is only ever evidence when the proxy overwrites it,
    # and a configured base URL makes the question moot.
    base = settings.public_base_url()
    if base:
        own = {base}
    else:
        scheme = _PAGE_SCHEME.get(connection.url.scheme, connection.url.scheme)
        own = {f"{scheme}://{connection.url.netloc}"}
        if settings.trust_proxy():
            # Behind TLS the app itself is spoken to over plain http, so its own idea of
            # the scheme is the wrong half of the origin the browser sent. The host is the
            # `Host` header either way, which a browser does not let a page choose.
            own.add(f"http://{connection.url.netloc}")
            own.add(f"https://{connection.url.netloc}")
    # Vite proxies `/api`, so the browser already considers itself same-origin in
    # development; these are only here for someone who points the SPA at the API directly.
    return own | set(settings.dev_cors_origins())


def _refused() -> JSONResponse:
    return JSONResponse(
        {"detail": "Petición rechazada: origen distinto al del servidor."}, status_code=403
    )
