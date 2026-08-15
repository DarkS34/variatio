"""Where the server keeps its own state, next to the instance it manages."""

import os
from datetime import timedelta
from pathlib import Path

from variant_generator import config
from variant_generator.workspace import Workspace


# One process, one workspace — for now. Every server module asks for it through this
# function rather than reading a path constant, so making it per-request later is a
# change here and nowhere else.
def workspace() -> Workspace:
    return config.default_workspace()


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "sí", "si")


# Everything that gets stricter in production reads this one answer, so there is a single
# switch to get wrong rather than five. Anything other than "development" is production:
# an unset or misspelled value must not be the permissive one.
def is_production() -> bool:
    return os.environ.get("VG_ENV", "development").strip().lower() not in ("development", "dev")


# Vite's dev server. It proxies `/api` and `/ws`, so the browser is already same-origin in
# development and CORS is not needed at all: the middleware is only mounted when someone
# explicitly asks for it with VG_DEV_CORS=1, and never in production.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def dev_cors_origins() -> list[str]:
    if is_production() or not _flag("VG_DEV_CORS"):
        return []
    return list(DEV_ORIGINS)


# AUTHENTICATION ------------------------------------------------------------------------

SESSION_COOKIE = "vg_session"

# Sliding, so a browser in daily use never gets logged out; absolute, so a stolen cookie
# cannot be renewed indefinitely. `TOUCH_INTERVAL` is what stops twenty requests on one
# page from writing the same row twenty times.
SESSION_SLIDING = timedelta(days=14)
SESSION_ABSOLUTE = timedelta(days=30)
SESSION_TOUCH_INTERVAL = timedelta(minutes=5)

INVITE_TTL = timedelta(days=7)
RESET_TTL = timedelta(minutes=45)

# `Secure` would make the browser drop the cookie over plain http, which is how the app is
# served in local development; in production Caddy terminates TLS and it goes on.
def cookie_secure() -> bool:
    return _flag("VG_COOKIE_SECURE", default=is_production())


# Where the links in an invitation or a reset mail point. Unset means "derive it from the
# request that asked", which is right for a single-domain deployment and for localhost.
def public_base_url() -> str | None:
    raw = os.environ.get("PUBLIC_BASE_URL", "").strip()
    return raw.rstrip("/") or None


# `X-Forwarded-For` is only evidence when something trustworthy wrote it. Reading it
# unconditionally would let anyone pick their own key for the per-IP rate limit, which is
# the same as having no per-IP limit at all.
def trust_proxy() -> bool:
    return _flag("VG_TRUST_PROXY", default=is_production())


# Attempts allowed per window, as (limit, seconds). Two keys are checked against each of
# these, the client IP and the account, so neither a spray nor a fixation gets through.
RATE_LIMITS: dict[str, tuple[int, float]] = {
    "login": (8, 300.0),
    "invite": (20, 3600.0),
    "forgot": (5, 900.0),
    "reset": (10, 900.0),
    "password": (10, 900.0),
}

# MAIL ----------------------------------------------------------------------------------

SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_SSL = _flag("SMTP_SSL")
SMTP_STARTTLS = _flag("SMTP_STARTTLS", default=True)
MAIL_FROM = os.environ.get("MAIL_FROM", "Generador de variantes <no-reply@localhost>")


def smtp_host() -> str:
    return os.environ.get("SMTP_HOST", "").strip()

WEB_DIST_DIR: Path = config.PROJECT_ROOT / "web" / "dist"

# Kept in memory for instant `?since=N` replay after a browser reload; the JSONL
# on disk is the long-term record.
EVENT_BUFFER_SIZE = 20_000

# A generated item is small; the payload that matters is the token stream.
MAX_TOKEN_CHARS = 200_000
