"""Every artifact write goes through here: atomic, backed up, reversible."""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from variatio.core import json_io
from variatio.core.workspace import Workspace

from .db import mirror


def read_json(path: Path) -> dict | list | None:
    if not Path(path).is_file():
        return None
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def sha256_of(path: Path | None) -> str | None:
    if path is None or not Path(path).is_file():
        return None
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


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
    snapshots = sorted(directory.iterdir(), reverse=True)
    for stale in snapshots[keep:]:
        stale.unlink(missing_ok=True)


def write_json(path: Path, data, ws: Workspace | None = None, artifact: str | None = None) -> Path:
    path = Path(path)
    if artifact and ws is not None:
        backup(ws, path, artifact)
    written = json_io.write_json(path, data)
    if artifact and ws is not None:
        mirror.mirror_file(ws, path)
    return written


def history(ws: Workspace, artifact: str) -> list[dict]:
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
    if snapshot_id != Path(snapshot_id).name:
        raise FileNotFoundError(f"No snapshot '{snapshot_id}' for '{artifact}'")
    source = ws.history_dir / artifact / snapshot_id
    if not source.is_file():
        raise FileNotFoundError(f"No snapshot '{snapshot_id}' for '{artifact}'")
    return write_json(Path(target), read_json(source), ws=ws, artifact=artifact)
