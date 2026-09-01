"""The installation's root paths, and the workspace a slug resolves to.

It imports only `dotenv` and `workspace`, which is what lets `settings.store` import it
with no cycle.
"""

import os
from pathlib import Path

from .dotenv import load_dotenv
from .workspace import Workspace

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", PROJECT_ROOT / "workspaces"))

# The installation's logs, one directory per workspace inside it. It is the same `logs/`
# the access log already writes into, and it is deliberately NOT under `workspaces/<slug>/`:
# a log is the installation's own record of what happened, it is not part of an instance,
# and `export-instance` must not carry it.
LOGS_DIR = Path(os.environ.get("VARIATIO_LOGS_DIR", PROJECT_ROOT / "logs"))


def workspace_logs_dir(slug: str) -> Path:
    """Return the log directory of the workspace called `slug`, creating it if needed.

    A slug is required here for the same reason it is required everywhere else: there is
    no default instance whose directory a nameless caller could land in.
    """
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Una asignatura se nombra: no hay instancia por defecto.")
    target = LOGS_DIR / slug
    target.mkdir(parents=True, exist_ok=True)
    return target


def workspace(slug: str) -> Workspace:
    """Return the workspace called `slug`; raises ValueError when no slug was given.

    There is no default instance to fall back to, so an empty slug is a caller's bug.
    """
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Una asignatura se nombra: no hay instancia por defecto.")
    return Workspace(WORKSPACES_DIR / slug, slug=slug)
