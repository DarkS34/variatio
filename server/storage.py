"""Every artifact write goes through here: atomic, backed up, reversible.

`write_json` wraps `core.json_io.write_json` to add the history snapshot and the database
mirror, and it is the only permitted second writer of a persisted artifact — the approval
hashes in the database are hashes of exactly those bytes.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from variatio.core import json_io
from variatio.core.workspace import Workspace

from .db import mirror


def read_json(path: Path) -> dict | list | None:
    """Read a JSON file, or None when there is none."""
    if not Path(path).is_file():
        return None
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data, ws: Workspace | None = None, artifact: str | None = None) -> Path:
    """Write a JSON file, snapshotting and mirroring it when it is a named artifact."""
    path = Path(path)
    if artifact and ws is not None:
        backup(ws, path, artifact)
    written = json_io.write_json(path, data)
    if artifact and ws is not None:
        mirror.mirror_file(ws, path)
    return written


def backup(ws: Workspace, path: Path, artifact: str) -> Path | None:
    """Snapshot the current file before overwriting it, so an edit is undoable."""
    path = Path(path)
    if not path.is_file():
        return None
    target_dir = ws.history_dir / artifact
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = target_dir / f"{stamp}{path.suffix}"
    shutil.copy2(path, target)
    _prune(target_dir, keep=30)
    return target


def _prune(directory: Path, keep: int) -> None:
    """Keep only the newest `keep` snapshots of one artifact.

    Sorted by name, which is the timestamp the snapshot was written under.
    """
    snapshots = sorted(directory.iterdir(), reverse=True)
    for stale in snapshots[keep:]:
        stale.unlink(missing_ok=True)


def history(ws: Workspace, artifact: str) -> list[dict]:
    """List an artifact's snapshots, newest first."""
    directory = ws.history_dir / artifact
    if not directory.is_dir():
        return []
    return [
        {
            "id": entry.name,
            "at": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(timespec="seconds"),
            "bytes": entry.stat().st_size,
        }
        for entry in sorted(directory.iterdir(), reverse=True)
    ]


def restore(ws: Workspace, artifact: str, snapshot_id: str, target: Path) -> Path:
    """Write one snapshot back over an artifact, snapshotting what it replaces.

    The id must be a bare filename, since it arrives in a request.
    """
    if snapshot_id != Path(snapshot_id).name:
        raise FileNotFoundError(f"No snapshot '{snapshot_id}' for '{artifact}'")
    source = ws.history_dir / artifact / snapshot_id
    if not source.is_file():
        raise FileNotFoundError(f"No snapshot '{snapshot_id}' for '{artifact}'")
    return write_json(Path(target), read_json(source), ws=ws, artifact=artifact)


def sha256_of(path: Path | None) -> str | None:
    """Digest a file's bytes, or None when there is no file."""
    if path is None or not Path(path).is_file():
        return None
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()
