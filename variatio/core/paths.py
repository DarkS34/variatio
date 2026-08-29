import os
from pathlib import Path

from .dotenv import load_dotenv
from .workspace import Workspace

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", PROJECT_ROOT / "workspaces"))

def workspace(slug: str) -> Workspace:
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Un workspace se nombra: no hay instancia por defecto.")
    return Workspace(WORKSPACES_DIR / slug, slug=slug)
