"""Where the server keeps its own state, next to the instance it manages."""

from pathlib import Path

from variant_generator import config
from variant_generator.workspace import Workspace


# One process, one workspace — for now. Every server module asks for it through this
# function rather than reading a path constant, so making it per-request later is a
# change here and nowhere else.
def workspace() -> Workspace:
    return config.default_workspace()

# Vite's dev server. In "local production" the API serves the built assets and
# this stops mattering.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

WEB_DIST_DIR: Path = config.PROJECT_ROOT / "web" / "dist"

# Kept in memory for instant `?since=N` replay after a browser reload; the JSONL
# on disk is the long-term record.
EVENT_BUFFER_SIZE = 20_000

# A generated item is small; the payload that matters is the token stream.
MAX_TOKEN_CHARS = 200_000
