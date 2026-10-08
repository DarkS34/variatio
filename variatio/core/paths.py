"""The installation's root paths, and the workspace a slug resolves to.

It imports only `dotenv` and `workspace` from the package, which is what lets
`settings.store` import it with no cycle.
"""

import os
from pathlib import Path

from loguru import logger

from .dotenv import load_dotenv
from .workspace import ARTIFACTS_DIRNAME, LEGACY_ARTIFACTS_DIRNAME, Workspace

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", PROJECT_ROOT / "workspaces"))

# The installation's logs, one directory per workspace inside it. It is the same `logs/`
# the access log already writes into, and it is deliberately NOT under `workspaces/<slug>/`:
# a log is the installation's own record of what happened, it is not part of an instance,
# and `export-instance` must not carry it.
LOGS_DIR = Path(os.environ.get("VARIATIO_LOGS_DIR", PROJECT_ROOT / "logs"))


def cerebras_budget_path() -> Path:
    """Return where the Cerebras ledger lives: `CEREBRAS_BUDGET_PATH`, else the user's state.

    Outside the tree on purpose. Cerebras applies its rate limits to the ORGANISATION, not
    to the key, so every installation of one account on this machine has to count against
    one ledger: one per tree lets each of them spend the whole quota. Sharing is therefore
    the default, and the variable exists for an installation whose key belongs to another
    account — the cheap mistake is the shared one, which only waits longer than it had to.
    """
    explicit = os.environ.get("CEREBRAS_BUDGET_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    state_home = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return base / "variatio" / "cerebras_budget.json"


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

    There is no default instance to fall back to, so an empty slug is a caller's bug. The one
    door every workspace is opened through, so it is where a tree still laid out the old way
    is brought up to date (`adopt_legacy_layout`).
    """
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Una asignatura se nombra: no hay instancia por defecto.")
    root = WORKSPACES_DIR / slug
    adopt_legacy_layout(root)
    return Workspace(root, slug=slug)


# The roots already looked at by this process: the check is a stat, and this door is passed
# on every request.
_ADOPTED: set[Path] = set()


def adopt_legacy_layout(root: Path) -> None:
    """Rename a workspace's `instance/` to `artifacts/`, once, if it still has the old name.

    The directory was renamed on 2026-10-08, and the trees on disk carry the old name until
    they are opened: nobody has to move anything by hand. The rename is atomic within one
    disk, and a second process that lost the race finds `artifacts/` and carries on. With both
    directories present nothing is touched — which of the two holds the subject is a person's
    call — and `artifacts/`, the one every path reads, is what the workspace runs on.
    """
    if root in _ADOPTED:
        return
    legacy = root / LEGACY_ARTIFACTS_DIRNAME
    current = root / ARTIFACTS_DIRNAME
    if legacy.is_dir() and current.exists():
        logger.warning(
            f"'{root}' holds both '{LEGACY_ARTIFACTS_DIRNAME}/' and '{ARTIFACTS_DIRNAME}/'; "
            f"'{ARTIFACTS_DIRNAME}/' is used and nothing is moved"
        )
    elif legacy.is_dir():
        try:
            legacy.rename(current)
            logger.info(f"'{root.name}': '{LEGACY_ARTIFACTS_DIRNAME}/' renamed '{ARTIFACTS_DIRNAME}/'")
        except FileNotFoundError:
            if not current.is_dir():
                raise
    _ADOPTED.add(root)
