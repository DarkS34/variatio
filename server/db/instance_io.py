"""Moving one workspace between the filesystem layout and the database.

`import_instance` is what keeps the curated graph you already have when the first
deployed version starts empty. `export_instance` is its inverse and the seed of the
worker's materializer: given a database and an empty directory, it writes back an
instance the existing pipeline can run against unchanged.
"""

import hashlib
import json
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from variatio import stages
from variatio.core import json_io
from variatio.core.workspace import Workspace as FsWorkspace

from . import repository as repo
from .layout import KINDS, artifact_paths
from .models import SLOT_CORPUS, SLOT_EXEMPLARS


def _slots(ws: FsWorkspace) -> dict[str, Path]:
    return {SLOT_CORPUS: ws.raw_corpus_dir, SLOT_EXEMPLARS: ws.raw_exemplars_dir}


def _read_json(path: Path):
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"No se pudo leer {path.name}; se omite: {exc}")
        return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _current_file(ws: FsWorkspace, kind: str) -> Path | None:
    if kind == stages.KNOWLEDGE_GRAPH:
        return stages.knowledge_graph_path(ws)
    if kind == stages.EXEMPLARS_PROFILE:
        return stages.exemplars_profile_path(ws)
    if kind == stages.EXEMPLARS_BANK:
        return ws.exemplars_bank_path if ws.exemplars_bank_path.is_file() else None
    return None


# The recorded hashes are of *files*; the database stores hashes of *content*. Rather than
# assume the two agree, the file hashes are used only for the question they can answer —
# was this approval still current, for the artifact and for everything it derives from? —
# and what gets stored is re-derived from the imported rows. A stale approval is simply not
# imported, which lands the artifact in `draft`: conservative, and never a false "approved".
def _approval_is_current(ws: FsWorkspace, kind: str, record: dict) -> bool:
    path = _current_file(ws, kind)
    if path is None or _file_sha256(path) != record.get("hash"):
        return False
    for up, recorded in (record.get("upstream") or {}).items():
        up_path = _current_file(ws, up)
        if up_path is None or _file_sha256(up_path) != recorded:
            return False
    return True


def import_instance(
    session: Session,
    ws: FsWorkspace,
    slug: str,
    name: str | None = None,
) -> dict:
    """Load a filesystem workspace into the database as one workspace row."""
    workspace = repo.ensure_workspace(session, slug, name)

    imported: list[str] = []
    for kind, stage_paths in artifact_paths(ws).items():
        for stage, path in stage_paths.items():
            content = _read_json(path)
            if content is None:
                continue
            repo.save_artifact(session, workspace.id, kind, stage, content)
            imported.append(f"{kind}/{stage}")

    approvals = 0
    state = _read_json(ws.review_state_path) or {}
    for kind, record in state.items():
        if not isinstance(record, dict) or record.get("status") != "approved":
            continue
        if not _approval_is_current(ws, kind, record):
            logger.info(f"[{kind}] la aprobación en disco ya estaba caducada; no se importa")
            continue

        artifact = repo.current_artifact(session, workspace.id, kind)
        if artifact is None:
            continue

        upstream = {}
        for up in record.get("upstream") or {}:
            up_artifact = repo.current_artifact(session, workspace.id, up)
            if up_artifact is not None:
                upstream[up] = up_artifact.sha256

        repo.approve(
            session,
            workspace.id,
            kind,
            sha256=artifact.sha256,
            upstream_hashes=upstream,
            artifact_id=artifact.id,
        )
        approvals += 1

    documents = 0
    for slot, directory in _slots(ws).items():
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            if not entry.is_file():
                continue
            repo.register_raw_document(
                session,
                workspace.id,
                slot,
                filename=entry.name,
                size=entry.stat().st_size,
                sha256=_file_sha256(entry),
                object_key=str(entry),
            )
            documents += 1

    summary = {
        "workspace": workspace.slug,
        "workspace_id": workspace.id,
        "artifacts": imported,
        "approvals": approvals,
        "raw_documents": documents,
    }
    logger.success(
        f"«{workspace.slug}» importado: {len(imported)} versión(es) de artefacto, "
        f"{approvals} aprobación(es), {documents} documento(s) fuente"
    )
    return summary


def export_instance(session: Session, slug: str, ws: FsWorkspace) -> dict:
    """Write a database workspace back out as the directory layout the stages read."""
    workspace = repo.get_workspace(session, slug)
    if workspace is None:
        raise LookupError(f"No workspace '{slug}' in the database")

    ws.instance_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for kind, stage_paths in artifact_paths(ws).items():
        for stage, path in stage_paths.items():
            artifact = repo.latest_artifact(session, workspace.id, kind, stage)
            if artifact is None:
                continue
            json_io.write_json(path, artifact.content)
            written.append(f"{kind}/{stage} v{artifact.version}")

    state = {}
    for kind in KINDS:
        approval = repo.get_approval(session, workspace.id, kind)
        if approval is None:
            continue
        state[kind] = {
            "status": "approved",
            "hash": approval.sha256,
            "upstream": approval.upstream_hashes or {},
            "at": approval.approved_at.isoformat(timespec="seconds"),
        }
    if state:
        json_io.write_json(ws.review_state_path, state)

    logger.success(f"«{slug}» exportado a {ws.root}: {len(written)} artefacto(s)")
    return {"workspace": slug, "root": str(ws.root), "artifacts": written, "approvals": len(state)}
