"""The two things a cookie-authenticated app needs in front of every request.

Once the session lives in a cookie the browser attaches it to *any* request it makes,
including one a page on another site caused. Same-origin plus `SameSite=Lax` already
stops most of it; checking the origin of every state-changing request is the part that
does not depend on the browser being recent.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from . import settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# `frame-ancestors` and `X-Frame-Options` say the same thing to two generations of
# browser. `unsafe-inline` survives only for styles: React writes element `style`
# attributes (the graph canvas among them) and CSP has no nonce for those.
CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": CSP,
}


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for header, value in HEADERS.items():
            response.headers.setdefault(header, value)
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

        fetch_site = request.headers.get("sec-fetch-site")
        if fetch_site and fetch_site not in ("same-origin", "none"):
            return _refused()

        origin = request.headers.get("origin")
        if origin and origin not in _allowed(request):
            return _refused()

        return await call_next(request)


def _allowed(request) -> set[str]:
    own = {f"{request.url.scheme}://{request.url.netloc}"}
    forwarded = request.headers.get("x-forwarded-host")
    if settings.trust_proxy() and forwarded:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        own.add(f"{proto}://{forwarded.split(',')[0].strip()}")
        own.add(f"http://{request.url.netloc}")
        own.add(f"https://{request.url.netloc}")
    base = settings.public_base_url()
    if base:
        own.add(base)
    # Vite proxies `/api`, so the browser already considers itself same-origin in
    # development; these are only here for someone who points the SPA at the API directly.
    return own | set(settings.dev_cors_origins())


def _refused() -> JSONResponse:
    return JSONResponse(
        {"detail": "Petición rechazada: origen distinto al del servidor."}, status_code=403
    )
