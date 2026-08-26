import json
from pathlib import Path

from loguru import logger

from variatio.core.workspace import Workspace as FsWorkspace

from . import repository as repo
from .layout import locate
from .session import session_scope


def mirror_artifact(slug: str, kind: str, stage: str, content) -> None:
    try:
        with session_scope() as session:
            workspace = repo.ensure_workspace(session, slug)
            repo.save_artifact(session, workspace.id, kind, stage, content)
    except Exception as exc:  # noqa: BLE001 - the file is written; only its reflection failed
        logger.warning(f"[bd] No se pudo reflejar «{kind}» de «{slug}»: {exc}")


def mirror_file(ws: FsWorkspace, path: Path) -> None:
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
        logger.warning(f"[bd] No se pudo reflejar «{kind}» de «{slug}»: {exc}")
