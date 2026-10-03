"""The tutor's conversations, one JSON file per conversation inside the workspace.

`<workspace>/tutor/user_<id>/<id>.json`, the same shape the generated exercises keep and for
the same reasons: the author's id names the directory, so privacy is where a reader looks
rather than a filter it applies, and every reader here takes an account and opens that
account's directory alone — `list_all` included, which walks them one by one for the
installation administrator's panel and nobody else. The id and never the username, because ids are not reused.

A conversation is written WHOLE after every change through `json_io.write_json`, and the
read-modify-write of one file is serialised by a lock per file: the route that appends the
student's message and the job that appends the tutor's reply touch the same file, and a turn
lasts seconds.

`pending` is the one field that says a reply is on its way: the id of the job writing it and
the index of the student turn it answers. A route refuses a second message while it is live;
when its job is gone — failed, cancelled, or lost to a restart — the student turn is marked
with why, and the conversation is free again.
"""

import json
import re
import secrets
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from variatio.core import json_io
from variatio.core.workspace import Workspace

from .. import paths

FORMAT = 1
AUTHOR_PREFIX = "user_"
STUDENT = "student"
TUTOR = "tutor"

# A title is the first message's opening, which is what a list of conversations is read by.
_TITLE_CHARS = 80

# `<UTC>-<six hex>`. Checked on every route, since it is joined to a path.
ID_PATTERN = re.compile(r"\A\d{8}T\d{6}Z-[0-9a-f]{6}\Z")
_AUTHOR_DIR = re.compile(rf"{AUTHOR_PREFIX}(\d+)")

_locks: defaultdict[Path, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()
_warned: set[Path] = set()


def lock_for(ws: Workspace, user_id: int, conversation_id: str) -> threading.Lock:
    """Return the lock that serialises every read-modify-write of one conversation's file."""
    with _locks_guard:
        return _locks[_path(ws, user_id, conversation_id)]


# WRITING -------------------------------------------------------------------------------


def create(
    ws: Workspace,
    user_id: int,
    message: str,
    opened_from: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """Start a conversation with its first message and return the record, already written."""
    moment = now or datetime.now(timezone.utc)
    record = {
        "format": FORMAT,
        "id": f"{_stamp(moment)}-{secrets.token_hex(3)}",
        "created_at": _iso(moment),
        "updated_at": _iso(moment),
        "title": _title(message),
        "opened_from": opened_from or {"kind": "message"},
        "state": {"focus": [], "trail": [], "verified": []},
        "turns": [{"role": STUDENT, "text": message, "at": _iso(moment)}],
        "pending": None,
    }
    write(ws, user_id, record)
    return record


def append_student(record: dict, message: str, now: datetime | None = None) -> int:
    """Append the student's message to a record in memory and return its index."""
    moment = now or datetime.now(timezone.utc)
    record["turns"].append({"role": STUDENT, "text": message, "at": _iso(moment)})
    record["updated_at"] = _iso(moment)
    return len(record["turns"]) - 1


def append_tutor(record: dict, text: str, details: dict, now: datetime | None = None) -> None:
    """Append the tutor's reply to a record in memory, with how it was made."""
    moment = now or datetime.now(timezone.utc)
    record["turns"].append({"role": TUTOR, "text": text, "at": _iso(moment), **details})
    record["updated_at"] = _iso(moment)


def mark_failed(record: dict, turn: int, reason: str) -> None:
    """Record on a student turn why it got no reply, and free the conversation."""
    if 0 <= turn < len(record["turns"]):
        record["turns"][turn]["failed"] = reason
    record["pending"] = None


def write(ws: Workspace, user_id: int, record: dict) -> str:
    """Write a whole record under its author, refusing an id this store would never read."""
    conversation_id = str(record.get("id") or "")
    if not ID_PATTERN.match(conversation_id):
        raise ValueError(f"Identificador de conversación no válido: «{conversation_id}»")
    json_io.write_json(_path(ws, user_id, conversation_id), record)
    return conversation_id


def delete(ws: Workspace, user_id: int, conversation_id: str) -> bool:
    """Delete one of this account's conversations, and say whether there was one."""
    if not ID_PATTERN.match(conversation_id or ""):
        return False
    path = _path(ws, user_id, conversation_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


# READING -------------------------------------------------------------------------------


def get(ws: Workspace, user_id: int, conversation_id: str) -> dict | None:
    """Return one of this account's conversations, or None — for a malformed id as well."""
    if not ID_PATTERN.match(conversation_id or ""):
        return None
    return _read(_path(ws, user_id, conversation_id))


def list_for(ws: Workspace, user_id: int) -> list[dict]:
    """Return this account's conversations, the most recently active first."""
    return _newest_first(author_dir(ws, user_id))


def list_all(ws: Workspace, author: int | None = None) -> list[tuple[int, dict]]:
    """Return every account's conversations with their author's id, the most recent first.

    The administrator's read and nobody else's; `author` narrows it to one account.
    """
    pairs = [
        (user_id, record)
        for user_id in authors(ws)
        if author is None or user_id == author
        for record in _newest_first(author_dir(ws, user_id))
    ]
    pairs.sort(key=lambda pair: str(pair[1].get("updated_at") or ""), reverse=True)
    return pairs


def authors(ws: Workspace) -> list[int]:
    """Return the ids of every account with a conversation here."""
    root = paths.conversations_dir(ws)
    if not root.is_dir():
        return []
    found = []
    for directory in sorted(root.iterdir()):
        match = _AUTHOR_DIR.fullmatch(directory.name)
        if directory.is_dir() and match:
            found.append(int(match.group(1)))
    return found


def count(ws: Workspace) -> int:
    """Count every conversation of the workspace, whoever had it."""
    root = paths.conversations_dir(ws)
    return sum(1 for _ in root.glob("*/*.json")) if root.is_dir() else 0


def author_dir(ws: Workspace, user_id: int) -> Path:
    """Return the directory one account's conversations live in."""
    return paths.conversations_dir(ws) / f"{AUTHOR_PREFIX}{int(user_id)}"


def _path(ws: Workspace, user_id: int, conversation_id: str) -> Path:
    """Return the file of one conversation."""
    return author_dir(ws, user_id) / f"{conversation_id}.json"


def _newest_first(directory: Path) -> list[dict]:
    """Read every record of one directory, the most recently active first."""
    if not directory.is_dir():
        return []
    records = [r for r in (_read(path) for path in directory.glob("*.json")) if r is not None]
    records.sort(key=lambda record: str(record.get("updated_at") or ""), reverse=True)
    return records


def _read(path: Path) -> dict | None:
    """Read one record, or None when it is missing or unreadable — said once per file."""
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        if path not in _warned:
            _warned.add(path)
            logger.warning(f"[tutor] Se salta una conversación ilegible '{path}': {exc}")
        return None
    return record if isinstance(record, dict) else None


def _title(message: str) -> str:
    """Return a conversation's title: the first line of its first message, clipped."""
    first = next((line.strip() for line in message.splitlines() if line.strip()), "")
    return first if len(first) <= _TITLE_CHARS else first[: _TITLE_CHARS - 1].rstrip() + "…"


def _stamp(moment: datetime) -> str:
    """Render a moment as the compact UTC stamp an id starts with."""
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iso(moment: datetime) -> str:
    """Render a moment as the UTC ISO string a record carries."""
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
