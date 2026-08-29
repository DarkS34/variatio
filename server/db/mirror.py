"""Reflecting a write into the database, best-effort.

The files stay the operational truth; these keep the rows beside them current. Any
database failure is ONE warning and never an exception — a hiccup must not break an edit
or a build. Each function opens its own short session, and `mirror_artifact` is
idempotent through the content hash.
"""

import json
from pathlib import Path

from loguru import logger

from variatio.core.workspace import Workspace as FsWorkspace

from . import repository as repo
from .layout import locate
from .session import session_scope


def mirror_artifact(slug: str, kind: str, stage: str, content) -> None:
    """Save this content as the workspace's current version of `kind`/`stage`."""
    try:
        with session_scope() as session:
            workspace = repo.ensure_workspace(session, slug)
            repo.save_artifact(session, workspace.id, kind, stage, content)
    except Exception as exc:  # noqa: BLE001 - the file is written; only its reflection failed
        _warn(kind, slug, exc)


def _warn(kind: str, slug: str, exc: Exception) -> None:
    """Say the mirror failed, and say WHETHER RETRYING COULD EVER WORK.

    Best-effort was never meant to mean indistinguishable. A database that is down comes
    back and the next write catches up; content the database REFUSES never will, and until
    somebody notices, the row simply stops keeping up with the file — measured on a
    reference installation, a bank whose extraction had left four NUL characters in it had
    a file of 151 items and a row of 152, and the only trace was this line.

    `refusal` is what keeps it readable: a `DBAPIError` stringifies to the whole statement
    plus every bound parameter, which for an artifact is hundreds of kilobytes.
    """
    from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError

    from . import refusal

    if isinstance(exc, (DataError, IntegrityError, ProgrammingError)):
        logger.error(
            f"[bd] La base de datos RECHAZA «{kind}» de «{slug}» y lo seguirá rechazando: "
            f"{refusal(exc)}"
        )
        return
    logger.warning(f"[bd] No se pudo reflejar «{kind}» de «{slug}»: {refusal(exc)}")


def mirror_file(ws: FsWorkspace, path: Path) -> None:
    """Mirror a JSON file that was just written, when it is one of the artifacts."""
    located = locate(ws, path)
    if located is None or not Path(path).is_file():
        return
    kind, stage = located
    try:
        with Path(path).open(encoding="utf-8") as f:
            content = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"[bd] No se pudo reflejar «{kind}» de «{ws.slug}»: {exc}")
        return
    mirror_artifact(ws.slug, kind, stage, content)


def mirror_approval(
    slug: str, kind: str, approved: bool, upstream: tuple[str, ...] = ()
) -> None:
    """Mirror an approval, re-deriving the upstream hashes from the current rows.

    `approved=False` deletes the row instead, which is what reopening a stage means.
    """
    try:
        with session_scope() as session:
            workspace = repo.get_workspace(session, slug)
            if workspace is None:
                return
            if not approved:
                repo.reopen(session, workspace.id, kind)
                return
            artifact = repo.current_artifact(session, workspace.id, kind)
            if artifact is None:
                return
            hashes = {}
            for up in upstream:
                up_artifact = repo.current_artifact(session, workspace.id, up)
                if up_artifact is not None:
                    hashes[up] = up_artifact.sha256
            repo.approve(
                session,
                workspace.id,
                kind,
                sha256=artifact.sha256,
                upstream_hashes=hashes,
                artifact_id=artifact.id,
            )
    except Exception as exc:  # noqa: BLE001 - the review state on disk is the truth
        _warn(kind, slug, exc)
