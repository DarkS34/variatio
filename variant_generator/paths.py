import os
from pathlib import Path

from .dotenv import load_dotenv
from .workspace import DEFAULT_SLUG, Workspace

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

# Every per-instance path lives on `Workspace`, never here: a path constant resolved at
# import time is exactly what makes two users overwrite each other's graph. What stays in
# this module is what is genuinely global — the root of the checkout and the directory the
# instances hang off.
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", PROJECT_ROOT / "workspaces"))

# `default` is a workspace like any other and lives where the others live. It used to be
# the single-user layout this repo always had, hanging off PROJECT_ROOT, which made the
# first instance a special case in every listing and put it somewhere no other instance
# could be. Moved into the tree on 2026-08-17 by explicit user request: one shape for every
# instance, and `workspaces/` as the only directory holding user data. The move is byte for
# byte — the `.npz` and the markdown cache are fingerprinted by content and not by path, so
# nothing was re-embedded.


def default_workspace() -> Workspace:
    return workspace(DEFAULT_SLUG)


def workspace(slug: str | None = None) -> Workspace:
    slug = slug or DEFAULT_SLUG
    return Workspace(WORKSPACES_DIR / slug, slug=slug)
