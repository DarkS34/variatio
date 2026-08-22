"""Where the server keeps its own state, next to the instance it manages."""

import os
import re
import shutil
from datetime import timedelta
from pathlib import Path

from variant_generator import paths
from variant_generator.workspace import DEFAULT_SLUG, Workspace

# One process now serves MANY workspaces, so there is no `workspace()` any more: a
# function with no argument is exactly the process-global that made two users overwrite
# each other's graph. Every server entry point resolves a slug — `require_member` does it
# once per request from the header or the account's active workspace — and passes the
# resulting `Workspace` down. A module that needs a path takes it as an argument.
#
# `default` is no longer a special case: now that its tree lives in `workspaces/default/`,
# resolution is the same for every instance, and all this function still contributes is
# that the server translates "no header" into the initial instance and into nothing else.
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


def workspace_for(slug: str | None) -> Workspace:
    return paths.workspace(slug)


def slug_error(slug: str) -> str | None:
    if slug == DEFAULT_SLUG:
        return f"'{DEFAULT_SLUG}' es el nombre reservado del workspace inicial."
    if not SLUG_PATTERN.match(slug):
        return (
            "El identificador admite minúsculas, cifras y guiones, entre 3 y 64 "
            "caracteres, y no puede empezar ni acabar en guión."
        )
    return None


# A workspace is a directory tree before it is a database row: the builders write files
# and the readers read them, so creating the row without the tree would leave every
# screen reporting a missing artifact for a reason nobody could act on.
def provision(ws: Workspace) -> None:
    for directory in (
        ws.instance_dir,
        ws.cache_dir,
        ws.raw_corpus_dir,
        ws.raw_exemplars_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


# La otra mitad de `provision`, y solo la usa el panel de administración: borrar un
# workspace de la base de datos y dejar su árbol en disco deja cientos de megas huérfanos
# bajo un slug que ya no consta en ninguna parte.
#
# La comprobación de que el directorio cuelga de `WORKSPACES_DIR` no es decorativa: aquí
# entra un slug que viene de una petición, y `shutil.rmtree` sobre una ruta mal resuelta no
# se puede deshacer. `Workspace.__post_init__` ya la resuelve, así que basta comparar.
def destroy(ws: Workspace) -> bool:
    root = ws.root
    parent = Path(paths.WORKSPACES_DIR).resolve()
    if root.parent != parent or root == parent:
        raise ValueError(f"'{root}' no está dentro de '{parent}': no se borra nada.")
    if not root.is_dir():
        return False
    shutil.rmtree(root)
    return True


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

WEB_DIST_DIR: Path = paths.PROJECT_ROOT / "web" / "dist"

# Kept in memory for instant `?since=N` replay after a browser reload; the JSONL
# on disk is the long-term record.
EVENT_BUFFER_SIZE = 20_000

# A generated item is small; the payload that matters is the token stream.
MAX_TOKEN_CHARS = 200_000
