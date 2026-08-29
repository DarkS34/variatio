"""The one writer of every JSON this system persists."""

import json
import os
from pathlib import Path


def write_json(path: str | Path, data, sort_keys: bool = False) -> Path:
    """Write `data` to `path` atomically, through a `.tmp` that replaces the file.

    A build, a tagging pass or an edit cancelled halfway must not leave half a file where
    an artifact should be: the next run would read it and fail far from the cause.

    The formatting is fixed because the approval hashes stored in the database are hashes
    of these bytes — a second writer differing in `indent` or `ensure_ascii` would
    silently make every approval look outdated.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o666)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=sort_keys)
    tmp.replace(path)
    return path
