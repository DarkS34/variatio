"""Conversations, one JSON file per conversation inside the workspace, private to their author.

`<workspace>/<folder>/user_<id>/<id>.json`, the same shape the generated exercises keep and for
the same reasons: the author's id names the directory, so privacy is where a reader looks
rather than a filter it applies, and every reader here takes an account and opens that
account's directory alone — `list_all` included, which walks them one by one for the
installation administrator's panel and nobody else. The id and never the username, because
ids are not reused.

A conversation is written WHOLE after every change through `json_io.write_json`, and the
read-modify-write of one file is serialised by a lock per file: the route that appends the
student's message and the job that appends the reply touch the same file, and a turn lasts
seconds.

`pending` is the one field that says a reply is on its way: the id of the job writing it and
the index of the student turn it answers. A route refuses a second message while it is live;
when its job is gone — failed, cancelled, or lost to a restart — the student turn is marked
with why, and the conversation is free again.

One `Store` per function (`apps.tutor.api.store`, `apps.chat.api.store`): its folder, the
role its replies are written under, the state a new conversation starts with, and the scope
its log lines carry.
"""

import json
import re
import secrets
import threading
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from variatio.core import json_io
from variatio.core.workspace import Workspace

FORMAT = 1
AUTHOR_PREFIX = "user_"
STUDENT = "student"

# Until something better titles it, a conversation is titled by its first message's opening,
# which is what a list of conversations is read by.
_TITLE_CHARS = 80

# `<UTC>-<six hex>`. Checked on every route, since it is joined to a path.
ID_PATTERN = re.compile(r"\A\d{8}T\d{6}Z-[0-9a-f]{6}\Z")
_AUTHOR_DIR = re.compile(rf"{AUTHOR_PREFIX}(\d+)")

# One lock per file, whichever function's: the paths never meet.
_locks: defaultdict[Path, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()
_warned: set[Path] = set()


class Store:
    """The conversations of one function, under `<workspace>/<folder>/`."""

    def __init__(
        self,
        folder: str,
        reply_role: str,
        scope: str,
        initial_state: Callable[[], dict] = dict,
    ) -> None:
        """Name the folder, the role replies are written under and the log's scope."""
        self.folder = folder
        self.reply_role = reply_role
        self.scope = scope
        self.initial_state = initial_state

    def lock_for(self, ws: Workspace, user_id: int, conversation_id: str) -> threading.Lock:
        """Return the lock that serialises every read-modify-write of one conversation's file."""
        with _locks_guard:
            return _locks[self._path(ws, user_id, conversation_id)]

    # WRITING ---------------------------------------------------------------------------

    def create(
        self,
        ws: Workspace,
        user_id: int,
        message: str,
        opened_from: dict | None = None,
        now: datetime | None = None,
        concept: str | None = None,
    ) -> dict:
        """Start a conversation with its first message and return the record, already written."""
        moment = now or datetime.now(timezone.utc)
        record = {
            "format": FORMAT,
            "id": f"{_stamp(moment)}-{secrets.token_hex(3)}",
            "created_at": _iso(moment),
            "updated_at": _iso(moment),
            "title": _title(message),
            "titled": False,
            "opened_from": opened_from or {"kind": "message"},
            "state": self.initial_state(),
            "turns": [_student_turn(message, moment, concept)],
            "pending": None,
        }
        self.write(ws, user_id, record)
        return record

    def append_reply(self, record: dict, text: str, details: dict, now: datetime | None = None) -> None:
        """Append a reply to a record in memory, with how it was made."""
        moment = now or datetime.now(timezone.utc)
        record["turns"].append({"role": self.reply_role, "text": text, "at": _iso(moment), **details})
        record["updated_at"] = _iso(moment)

    def write(self, ws: Workspace, user_id: int, record: dict) -> str:
        """Write a whole record under its author, refusing an id this store would never read."""
        conversation_id = str(record.get("id") or "")
        if not ID_PATTERN.match(conversation_id):
            raise ValueError(f"Identificador de conversación no válido: «{conversation_id}»")
        json_io.write_json(self._path(ws, user_id, conversation_id), record)
        return conversation_id

    def delete(self, ws: Workspace, user_id: int, conversation_id: str) -> bool:
        """Delete one of this account's conversations, and say whether there was one."""
        if not ID_PATTERN.match(conversation_id or ""):
            return False
        path = self._path(ws, user_id, conversation_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    # READING ---------------------------------------------------------------------------

    def get(self, ws: Workspace, user_id: int, conversation_id: str) -> dict | None:
        """Return one of this account's conversations, or None — for a malformed id as well."""
        if not ID_PATTERN.match(conversation_id or ""):
            return None
        return self._read(self._path(ws, user_id, conversation_id))

    def list_for(self, ws: Workspace, user_id: int) -> list[dict]:
        """Return this account's conversations, the most recently active first."""
        return self._newest_first(self.author_dir(ws, user_id))

    def list_all(self, ws: Workspace, author: int | None = None) -> list[tuple[int, dict]]:
        """Return every account's conversations with their author's id, the most recent first.

        The administrator's read and nobody else's; `author` narrows it to one account.
        """
        pairs = [
            (user_id, record)
            for user_id in self.authors(ws)
            if author is None or user_id == author
            for record in self._newest_first(self.author_dir(ws, user_id))
        ]
        pairs.sort(key=lambda pair: str(pair[1].get("updated_at") or ""), reverse=True)
        return pairs

    def authors(self, ws: Workspace) -> list[int]:
        """Return the ids of every account with a conversation here."""
        root = self.root(ws)
        if not root.is_dir():
            return []
        found = []
        for directory in sorted(root.iterdir()):
            match = _AUTHOR_DIR.fullmatch(directory.name)
            if directory.is_dir() and match:
                found.append(int(match.group(1)))
        return found

    def count(self, ws: Workspace) -> int:
        """Count every conversation of the workspace, whoever had it."""
        root = self.root(ws)
        return sum(1 for _ in root.glob("*/*.json")) if root.is_dir() else 0

    def root(self, ws: Workspace) -> Path:
        """Return the directory every author's conversations live under."""
        return ws.root / self.folder

    def author_dir(self, ws: Workspace, user_id: int) -> Path:
        """Return the directory one account's conversations live in."""
        return self.root(ws) / f"{AUTHOR_PREFIX}{int(user_id)}"

    def read_file(self, path: Path) -> dict | None:
        """Return the record one file holds, or None when it is missing or unreadable."""
        return self._read(path)

    def _path(self, ws: Workspace, user_id: int, conversation_id: str) -> Path:
        """Return the file of one conversation."""
        return self.author_dir(ws, user_id) / f"{conversation_id}.json"

    def _newest_first(self, directory: Path) -> list[dict]:
        """Read every record of one directory, the most recently active first."""
        if not directory.is_dir():
            return []
        records = [r for r in (self._read(path) for path in directory.glob("*.json")) if r is not None]
        records.sort(key=lambda record: str(record.get("updated_at") or ""), reverse=True)
        return records

    def _read(self, path: Path) -> dict | None:
        """Read one record, or None when it is missing or unreadable — said once per file."""
        if not path.is_file():
            return None
        try:
            with path.open(encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            if path not in _warned:
                _warned.add(path)
                logger.warning(f"[{self.scope}] Se salta una conversación ilegible '{path}': {exc}")
            return None
        return record if isinstance(record, dict) else None


def append_student(
    record: dict, message: str, now: datetime | None = None, concept: str | None = None
) -> int:
    """Append the student's message to a record in memory and return its index."""
    moment = now or datetime.now(timezone.utc)
    record["turns"].append(_student_turn(message, moment, concept))
    record["updated_at"] = _iso(moment)
    return len(record["turns"]) - 1


def mark_failed(record: dict, turn: int, reason: str) -> None:
    """Record on a student turn why it got no reply, and free the conversation."""
    if 0 <= turn < len(record["turns"]):
        record["turns"][turn]["failed"] = reason
    record["pending"] = None


def _student_turn(message: str, moment: datetime, concept: str | None) -> dict:
    """Return a student's turn, with the concept they chose it to be about when they did.

    The concept travels on the turn and not on the job that answers it, like the text: a
    job's parameters are heard by the whole workspace, and what one student asks about is
    theirs.
    """
    turn = {"role": STUDENT, "text": message, "at": _iso(moment)}
    if concept:
        turn["concept"] = concept
    return turn


def _title(message: str) -> str:
    """Return a conversation's first title: the first line of its first message, clipped."""
    first = next((line.strip() for line in message.splitlines() if line.strip()), "")
    return first if len(first) <= _TITLE_CHARS else first[: _TITLE_CHARS - 1].rstrip() + "…"


def _stamp(moment: datetime) -> str:
    """Render a moment as the compact UTC stamp an id starts with."""
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iso(moment: datetime) -> str:
    """Render a moment as the UTC ISO string a record carries."""
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
