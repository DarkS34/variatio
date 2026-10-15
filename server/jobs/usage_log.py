"""What every job's model calls cost, one line per job: `logs/<slug>/usage.jsonl`.

The measured cost of the system (the class plan's phase 9, 2026-10-15): a job's result says
what its calls cost while the queue remembers it, and this file keeps it — the kind of job,
when it ended and how, and its tokens by phase, engine and model. Never a text and never who
asked: a cost is the subject's, not a person's. `system usage` reads it back.

Appended under a lock, one JSON object per line, and best-effort: a cost that cannot be
written is one warning, never a failed job.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from variatio.core import paths

FILE_NAME = "usage.jsonl"

_lock = threading.Lock()


def path_for(slug: str) -> Path:
    """Return the usage file of one workspace, creating its directory."""
    return paths.workspace_logs_dir(slug) / FILE_NAME


def append(slug: str, kind: str, status: str, summary: dict, finished_at: float) -> None:
    """Keep one job's cost; nothing for a job that called no model."""
    if not summary.get("calls"):
        return
    line = {
        "at": datetime.fromtimestamp(finished_at, timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "status": status,
        **summary,
    }
    try:
        with _lock, path_for(slug).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning(f"[consumo] No se pudo apuntar lo que gastó «{kind}»: {exc}")


def read(slug: str) -> list[dict]:
    """Read every job's cost kept for one workspace, skipping a line that does not parse."""
    path = path_for(slug)
    if not path.is_file():
        return []
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
