"""Where the server keeps its own state, next to the instance it manages."""

import os
import re
import shutil
from datetime import timedelta
from pathlib import Path

from variatio.core import paths
from variatio.core.workspace import DEFAULT_SLUG, Workspace

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


# The other half of `provision`, used only by the administration panel: deleting a
# workspace from the database while leaving its tree on disk leaves hundreds of orphaned
# megabytes under a slug that is no longer on record anywhere.
#
# The check that the directory hangs from `WORKSPACES_DIR` is not decorative: the slug
# arriving here comes from a request, and `shutil.rmtree` on a mis-resolved path cannot
# be undone. `Workspace.__post_init__` already resolves it, so comparing is enough.
def destroy(ws: Workspace) -> bool:
    root = ws.root
    parent = Path(paths.WORKSPACES_DIR).resolve()
    if root.parent != parent or root == parent:
        raise ValueError(f"'{root}' no está dentro de '{parent}': no se borra nada.")
    if not root.is_dir():
        return False
    shutil.rmtree(root)
    return True


def _tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


# What each part of the tree weighs. `instance` excludes the host state it contains, which
# is reported on its own: the history is the one thing that grows without a build.
def disk_usage(ws: Workspace) -> dict[str, int]:
    history = _tree_size(ws.history_dir)
    runs = _tree_size(ws.runs_dir)
    instance = _tree_size(ws.instance_dir) - history - runs
    usage = {
        "raw": _tree_size(ws.raw_dir),
        "instance": max(0, instance),
        "cache": _tree_size(ws.cache_dir),
        "history": history + runs,
    }
    usage["total"] = sum(usage.values())
    return usage


# The regenerable half of `cache/`: the vectors and the converted markdown, which the next
# index or build rewrites from the artifacts. The concept descriptions and the corpus
# anchoring stay — they are written by the model against the corpus and cost a long run,
# and emptying a stage is where they go when the artifact they describe goes.
def clear_cache(ws: Workspace) -> dict:
    targets = [ws.cache_dir / "embeddings", ws.markdown_cache_dir]
    removed = 0
    freed = 0
    for target in targets:
        if not target.is_dir():
            continue
        for entry in target.rglob("*"):
            if entry.is_file():
                freed += entry.stat().st_size
                removed += 1
        shutil.rmtree(target)
    return {"files_removed": removed, "bytes_freed": freed}


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "sí", "si")


# Everything that gets stricter in production reads this one answer, so there is a single
# switch to get wrong rather than five. Anything other than "development" is production:
# an unset or misspelled value must not be the permissive one.
def is_production() -> bool:
    return os.environ.get("VARIATIO_ENV", "development").strip().lower() not in ("development", "dev")


# Vite's dev server. It proxies `/api` and `/ws`, so the browser is already same-origin in
# development and CORS is not needed at all: the middleware is only mounted when someone
# explicitly asks for it with VARIATIO_DEV_CORS=1, and never in production.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def dev_cors_origins() -> list[str]:
    if is_production() or not _flag("VARIATIO_DEV_CORS"):
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
    return _flag("VARIATIO_COOKIE_SECURE", default=is_production())


# Where the links in an invitation or a reset mail point. Unset means "derive it from the
# request that asked", which is right for a single-domain deployment and for localhost.
def public_base_url() -> str | None:
    raw = os.environ.get("PUBLIC_BASE_URL", "").strip()
    return raw.rstrip("/") or None


# `X-Forwarded-For` is only evidence when something trustworthy wrote it. Reading it
# unconditionally would let anyone pick their own key for the per-IP rate limit, which is
# the same as having no per-IP limit at all.
def trust_proxy() -> bool:
    return _flag("VARIATIO_TRUST_PROXY", default=is_production())


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
