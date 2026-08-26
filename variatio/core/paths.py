import os
from pathlib import Path

from .dotenv import load_dotenv
from .workspace import Workspace

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

# Every per-instance path lives on `Workspace`, never here: a path constant resolved at
# import time is exactly what makes two users overwrite each other's graph. What stays in
# this module is what is genuinely global — the root of the checkout and the directory the
# instances hang off.
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", PROJECT_ROOT / "workspaces"))

# There is no default instance. Until 2026-08-26 an omitted slug resolved to `default`, a
# workspace the repository shipped and every entry point fell back to, so «no dijo cuál»
# and «dijo `default`» were the same request — and an installation with no workspaces at
# all was not a state the code could express. It is one now: having none is normal, an
# account creates its own, and a caller that does not name one is a caller with nothing to
# read. `default` survives as an ordinary slug with no privileges, like `aula` or `cs101`.


def workspace(slug: str) -> Workspace:
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Un workspace se nombra: no hay instancia por defecto.")
    return Workspace(WORKSPACES_DIR / slug, slug=slug)
