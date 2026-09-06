"""The server's own configuration: workspace trees, environment switches, cookies, mail.

Everything here is the installation's rather than a workspace's, and everything that reads
the environment reads it through one function, so there is a single switch to get wrong
rather than five. None of it is a SETTING — `variatio/settings/` is the settings registry.
"""

import os
import re
import shutil
from datetime import timedelta
from pathlib import Path

from variatio.core import paths
from variatio.core.workspace import Workspace

# `\A`/`\Z` and not `^`/`$`: Python's `$` also matches just before a trailing newline, so
# `abc\n` would pass as a slug while `paths.workspace` stripped it back to `abc` — two rows
# pointing at one directory, either able to delete the other's tree. No name is reserved.
SLUG_PATTERN = re.compile(r"\A[a-z0-9][a-z0-9-]{1,62}[a-z0-9]\Z")


def workspace_for(slug: str) -> Workspace:
    """Resolve a slug to its `Workspace`.

    There is deliberately no no-argument `workspace()`: that IS the process global which
    made two users overwrite each other's graph. Every entry point resolves a slug once and
    passes the result down.
    """
    return paths.workspace(slug)


def slug_error(slug: str) -> str | None:
    """Say what is wrong with a proposed workspace slug, or return None."""
    if not SLUG_PATTERN.match(slug):
        return (
            "El identificador admite minúsculas, cifras y guiones, entre 3 y 64 "
            "caracteres, y no puede empezar ni acabar en guión."
        )
    return None


def provision(ws: Workspace) -> None:
    """Create a workspace's directory tree.

    A workspace is a tree before it is a row: the row without the tree leaves every screen
    reporting a missing artifact for a reason nobody could act on.
    """
    for directory in (
        ws.instance_dir,
        ws.cache_dir,
        ws.raw_corpus_dir,
        ws.raw_exemplars_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _contained_root(ws: Workspace) -> Path:
    """Return the workspace root, refusing anything that is not a direct child of the tree.

    Not decorative: the slug arrives in a request and `shutil.rmtree` on a mis-resolved
    path cannot be undone. `Workspace.__post_init__` already resolves it, so comparing is
    enough.
    """
    root = ws.root
    parent = Path(paths.WORKSPACES_DIR).resolve()
    if root.parent != parent or root == parent:
        raise ValueError(f"'{root}' no está dentro de '{parent}': no se borra nada.")
    return root


def destroy(ws: Workspace) -> bool:
    """Delete a workspace's whole tree, and report whether there was one."""
    root = _contained_root(ws)
    if not root.is_dir():
        return False
    shutil.rmtree(root)
    return True


def _tree_size(path: Path) -> int:
    """Total the bytes of a file or of everything under a directory."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


def disk_usage(ws: Workspace) -> dict[str, int]:
    """What each part of the tree weighs, by role.

    `instance` excludes the host state it contains, which is reported on its own: the
    history is the one thing that grows without a build.
    """
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


def clear_cache(ws: Workspace) -> dict:
    """Empty the regenerable half of `cache/`: the vectors and the converted markdown.

    The concept descriptions and the corpus anchoring stay — they cost a long model run,
    and emptying a stage is what removes them with the artifact they describe.
    """
    root = _contained_root(ws)
    targets = [ws.cache_dir / "embeddings", ws.markdown_cache_dir]
    removed = 0
    freed = 0
    for target in targets:
        if not target.is_dir():
            continue
        if not target.resolve().is_relative_to(root):
            continue
        for entry in target.rglob("*"):
            if entry.is_file():
                freed += entry.stat().st_size
                removed += 1
        shutil.rmtree(target)
    return {"files_removed": removed, "bytes_freed": freed}


def _flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "sí", "si")


def is_production() -> bool:
    """The one switch everything that gets stricter in production reads.

    Anything other than «development» is production: an unset or misspelled value must not
    be the permissive one.
    """
    return os.environ.get("VARIATIO_ENV", "development").strip().lower() not in ("development", "dev")


# Vite's dev server, which proxies `/api` and `/ws` — so the browser is already
# same-origin in development and these are only for pointing the SPA straight at the API.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def dev_cors_origins() -> list[str]:
    """The CORS origins to allow, which is none unless VARIATIO_DEV_CORS asks in development."""
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


def cookie_secure() -> bool:
    """Whether the session cookie carries `Secure`.

    Off in local development, where the app is served over plain http and a browser would
    drop the cookie; on in production, where Caddy terminates TLS.
    """
    return _flag("VARIATIO_COOKIE_SECURE", default=is_production())


def session_cookie() -> str:
    """The session cookie's name, `__Host-` prefixed wherever the cookie is `Secure`.

    The prefix buys a browser-enforced version of preconditions the cookie already meets:
    no subdomain and no plain-http page can overwrite the session. It cannot be a literal,
    because a browser refuses a `__Host-` cookie without `Secure`. Every read, write and
    delete goes through here, or login and logout disagree about which cookie they mean.
    """
    return f"__Host-{SESSION_COOKIE}" if cookie_secure() else SESSION_COOKIE


def public_base_url() -> str | None:
    """Where the links in an invitation or a reset mail point.

    None means «derive it from the request that asked», which is right for a single-domain
    deployment and for localhost.
    """
    raw = os.environ.get("PUBLIC_BASE_URL", "").strip()
    return raw.rstrip("/") or None


def trust_proxy() -> bool:
    """Whether `X-Forwarded-*` may be believed.

    Only evidence when something trustworthy wrote it: read unconditionally, anyone could
    pick their own key for the per-IP rate limit, which is the same as having none.
    """
    return _flag("VARIATIO_TRUST_PROXY", default=is_production())


# Attempts allowed per window, as (limit, seconds). Two keys are checked against each of
# these, the client IP and the account, so neither a spray nor a fixation gets through.
# `accept` is the one whose second key is not an account: there is no account yet, and the
# username is precisely what somebody holding a link varies to read «ya está cogido» off
# it, so the key there is the invitation itself.
RATE_LIMITS: dict[str, tuple[int, float]] = {
    "login": (8, 300.0),
    "invite": (20, 3600.0),
    "accept": (10, 3600.0),
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
MAIL_FROM = os.environ.get("MAIL_FROM", "Variatio <no-reply@localhost>")


def smtp_host() -> str:
    """The SMTP server to send through, empty when the installation configures none."""
    return os.environ.get("SMTP_HOST", "").strip()


WEB_DIST_DIR: Path = paths.PROJECT_ROOT / "web" / "dist"

# Kept in memory for instant `?since=N` replay after a browser reload; the JSONL
# on disk is the long-term record.
EVENT_BUFFER_SIZE = 20_000

# A generated item is small; the payload that matters is the token stream.
MAX_TOKEN_CHARS = 200_000
