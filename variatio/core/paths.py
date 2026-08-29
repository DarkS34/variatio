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

def workspace(slug: str) -> Workspace:
    """Return the workspace called `slug`; raises ValueError when no slug was given.

    There is no default instance to fall back to, so an empty slug is a caller's bug.
    """
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Un workspace se nombra: no hay instancia por defecto.")
    return Workspace(WORKSPACES_DIR / slug, slug=slug)
