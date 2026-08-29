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


def _socket_origin() -> str:
    """Name the WebSocket origin for `connect-src`, or nothing when none is declared.

    It grants nothing `'self'` does not already cover and exists for browsers predating
    CSP3's rule that `'self'` matches a same-origin `wss:` (Safari below 16). A bare `ws:`
    or `wss:` here would be a scheme source matching every host there is.
    """
    base = settings.public_base_url()
    if not base:
        return ""
    split = urlsplit(base)
    if not split.hostname:
        return ""
    scheme = "wss" if split.scheme == "https" else "ws"
    return f" {scheme}://{split.netloc}"


def csp() -> str:
    """Build the Content-Security-Policy header.

    `unsafe-inline` survives for styles alone: React writes element `style` attributes, the
    graph canvas among them, and CSP has no nonce for those.
    """
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


# `X-Frame-Options` says what `frame-ancestors` says, to an older generation of browser.
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}

# Six months, `includeSubDomains` because the session cookie is not host-only, and NO
# `preload`: that one is compiled into browsers and unsetting the header does not undo it,
# so it is the user's decision. Sent only where `cookie_secure()` says TLS terminates in
# front of us, or development would pin localhost to https for six months.
HSTS = "max-age=15552000; includeSubDomains"


class SecurityHeaders(BaseHTTPMiddleware):
    """Stamp the security headers on every response, refusals included."""

    async def dispatch(self, request, call_next):
        """Add the headers a response does not already carry."""
        response = await call_next(request)
        for header, value in HEADERS.items():
            response.headers.setdefault(header, value)
        response.headers.setdefault("Content-Security-Policy", csp())
        if settings.cookie_secure():
            response.headers.setdefault("Strict-Transport-Security", HSTS)
        return response


class OriginCheck(BaseHTTPMiddleware):
    """Refuse a state-changing request that shows positive evidence of being cross-site."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the application."""
        super().__init__(app)

    async def dispatch(self, request, call_next):
        """Let a safe method through, and refuse anything `cross_site` recognises."""
        if request.method in SAFE_METHODS:
            return await call_next(request)
        if cross_site(request):
            return _refused()
        return await call_next(request)


def cross_site(connection) -> bool:
    """Report positive evidence that a connection came from another site.

    Positive evidence, not proof of same-site: a request carrying neither `Sec-Fetch-Site`
    nor `Origin` is a script or a CLI, and CSRF needs a browser, which sends one of the
    two. Takes an `HTTPConnection` rather than a `Request` because `BaseHTTPMiddleware`
    short-circuits every non-`http` scope, so `/ws` never reaches `OriginCheck` and asks
    for itself — one reading of «same site», not two.
    """
    fetch_site = connection.headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in ("same-origin", "none"):
        return True
    origin = connection.headers.get("origin")
    return bool(origin and origin not in _allowed(connection))


# A handshake arrives as `ws://`/`wss://` while the browser's `Origin` is always the page's
# `http://`/`https://`, so comparing the two literally refuses every socket.
_PAGE_SCHEME = {"ws": "http", "wss": "https"}


def _allowed(connection) -> set[str]:
    """The origins that count as this app's own.

    A configured `PUBLIC_BASE_URL` is used verbatim and nothing is derived from the
    request: with `trust_proxy()` on, an attacker sending both `Origin: https://evil.com`
    and `X-Forwarded-Host: evil.com` would otherwise have their own origin admitted here.
    """
    base = settings.public_base_url()
    if base:
        own = {base}
    else:
        scheme = _PAGE_SCHEME.get(connection.url.scheme, connection.url.scheme)
        own = {f"{scheme}://{connection.url.netloc}"}
        if settings.trust_proxy():
            # Behind TLS the app is spoken to over plain http, so its own idea of the
            # scheme is the wrong half of the origin the browser sent. The host is the
            # `Host` header either way, which a browser does not let a page choose.
            own.add(f"http://{connection.url.netloc}")
            own.add(f"https://{connection.url.netloc}")
    return own | set(settings.dev_cors_origins())


def _refused() -> JSONResponse:
    """Return the 403 a cross-site request gets."""
    return JSONResponse(
        {"detail": "Petición rechazada: origen distinto al del servidor."}, status_code=403
    )
