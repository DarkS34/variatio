"""A subject's slug: resolving it to its paths, and checking a new one.

There is deliberately no no-argument `workspace()`: every path of a subject is reached from
its slug through `workspace_for`. A subject's tree on disk (provisioning, measuring,
deleting) is `server/workspaces/trees.py`; the environment's switches (production, cookies,
mail, limits) are `environment.py`, beside it.
"""

import re

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
