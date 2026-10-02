"""The exercises each account has generated, one JSON file per exercise inside the workspace.

`<workspace>/generations/user_<id>/<id>.json`. The author's id names the directory, so
privacy is where a reader looks rather than a filter it applies: every reader here takes an
account and opens that account's directory alone, except `list_all`, which only the
installation administrator's panel calls. The id and never the username, because ids
are not reused — a new account taking a deleted one's name must not inherit its exercises.
The `user_` prefix is for whoever lists the tree by hand.

One file per exercise, so no two writers share one: the remote lane runs up to four jobs of
one workspace at once. `json_io.write_json` replaces each file whole, so a run cancelled
halfway leaves complete files and nothing else.

A record keeps the commission as it was asked (`commission`) beside what actually ran
(`resolved`), the hashes of the artifacts it was generated against, the prompt of the
accepted attempt and the output: a statement without its parameters can be read but neither
judged nor reproduced. Format 0 is a row exported from the retired `generations` table; what
that table never kept is null there, never reconstructed.

Every read lists the directory, which is enough for the thousands a workspace holds at most.
An unreadable file is warned about once and skipped: it never empties a listing.
"""

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from variatio.core import json_io
from variatio.core.workspace import Workspace

FORMAT = 1
LEGACY_FORMAT = 0
ORPHANED = "_orphaned"
AUTHOR_PREFIX = "user_"

# `\A`/`\Z` for the reason `installation.SLUG_PATTERN` gives. A new id is
# `<UTC>-<job>-<index>`; one exported from the table is `<UTC>-db<row id>`. Checked on every
# route, since it is joined to a path.
ID_PATTERN = re.compile(r"\A\d{8}T\d{6}Z-[0-9a-z]{1,32}(?:-\d{1,6})?\Z")

_AUTHOR_DIR = re.compile(rf"{AUTHOR_PREFIX}(\d+)")

_warned: set[Path] = set()


# WRITING -------------------------------------------------------------------------------


def save(
    ws: Workspace,
    user_id: int | None,
    job_id: str | None,
    index: int,
    body: dict,
    now: datetime | None = None,
) -> str:
    """Write one validated exercise as a file of its own and return its id.

    The id sorts by date and is unique without a counter: the job and the item's position
    in it already are. Both are stamped into `job` here too, so the record cannot disagree
    with its own name — the position is what orders a batch written within one second.
    """
    moment = now or datetime.now(timezone.utc)
    token = re.sub(r"[^0-9a-z]", "", (job_id or "").lower())[:32] or "nojob"
    record = {
        "format": FORMAT,
        "id": f"{stamp(moment)}-{token}-{int(index)}",
        "created_at": iso(moment),
        **body,
        "job": {**(body.get("job") or {}), "id": job_id, "index": int(index)},
        "promoted_item_id": body.get("promoted_item_id"),
    }
    return write(ws, user_id, record)


def mark_promoted(ws: Workspace, user_id: int, record: dict, item_id: str) -> dict:
    """Record which bank item this exercise became, and return the record as rewritten."""
    updated = {**record, "promoted_item_id": item_id}
    write(ws, user_id, updated)
    return updated


def write(ws: Workspace, user_id: int | None, record: dict) -> str:
    """Write a whole record under its author, refusing an id this store would never read."""
    generation_id = str(record.get("id") or "")
    if not ID_PATTERN.match(generation_id):
        raise ValueError(f"Identificador de ejercicio no válido: «{generation_id}»")
    json_io.write_json(author_dir(ws, user_id) / f"{generation_id}.json", record)
    return generation_id


def delete(ws: Workspace, user_id: int, generation_id: str) -> bool:
    """Delete one of this account's exercises, and say whether there was one."""
    if not ID_PATTERN.match(generation_id or ""):
        return False
    path = author_dir(ws, user_id) / f"{generation_id}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True


# READING -------------------------------------------------------------------------------


def list_for(
    ws: Workspace,
    user_id: int,
    concept: str | None = None,
    item_type: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return one page of this account's exercises, newest first, and the total matched."""
    records = [
        r for r in _newest_first(ws, user_id) if _matches(r, concept, item_type, query)
    ]
    return records[offset : offset + limit], len(records)


def list_all(
    ws: Workspace,
    author: int | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[int | None, dict]], int]:
    """Return one page of every account's exercises, newest first, each with its author's id.

    The administrator's read and nobody else's: the orphaned directory's author is None.
    `author` narrows it to one account's directory.
    """
    pairs = [
        (user_id, record)
        for user_id in authors(ws)
        if author is None or user_id == author
        for record in _newest_first(ws, user_id)
        if _matches(record, None, None, query)
    ]
    pairs.sort(key=lambda pair: _order(pair[1]), reverse=True)
    return pairs[offset : offset + limit], len(pairs)


def authors(ws: Workspace) -> list[int | None]:
    """Return the ids of every account with a directory here, None for the orphaned one."""
    if not ws.generations_dir.is_dir():
        return []
    found: list[int | None] = []
    for directory in sorted(ws.generations_dir.iterdir()):
        if not directory.is_dir():
            continue
        match = _AUTHOR_DIR.fullmatch(directory.name)
        if match:
            found.append(int(match.group(1)))
        elif directory.name == ORPHANED:
            found.append(None)
    return found


def get(ws: Workspace, user_id: int, generation_id: str) -> dict | None:
    """Return one of this account's exercises, or None — for a malformed id as well."""
    if not ID_PATTERN.match(generation_id or ""):
        return None
    return _read(author_dir(ws, user_id) / f"{generation_id}.json")


def recent_items(
    ws: Workspace,
    user_id: int,
    item_type: str | None = None,
    concepts: list[str] | None = None,
    limit: int = 12,
) -> list[dict]:
    """Return this account's most recent items of one modality that share a concept.

    The account's own and never the workspace's: what this feeds is the "no repitas estos"
    block of somebody's prompt, and a colleague's statement there would reach them by
    another door than the one that is closed.
    """
    wanted = set(concepts or [])
    items: list[dict] = []
    for record in _newest_first(ws, user_id):
        if item_type and item_type_of(record) != item_type:
            continue
        if wanted and not wanted.intersection(concepts_of(record)):
            continue
        items.append(dict(item_of(record)))
        if len(items) >= limit:
            break
    return items


def count(ws: Workspace) -> int:
    """Count every exercise of the workspace, whoever wrote it."""
    if not ws.generations_dir.is_dir():
        return 0
    return sum(1 for _ in ws.generations_dir.glob("*/*.json"))


def count_by_author(workspaces: Iterable[Workspace]) -> dict[int, int]:
    """Count each account's exercises across these workspaces, leaving out the orphaned."""
    counts: dict[int, int] = {}
    for ws in workspaces:
        if not ws.generations_dir.is_dir():
            continue
        for directory in ws.generations_dir.iterdir():
            match = _AUTHOR_DIR.fullmatch(directory.name)
            if directory.is_dir() and match:
                user_id = int(match.group(1))
                counts[user_id] = counts.get(user_id, 0) + sum(1 for _ in directory.glob("*.json"))
    return counts


def _newest_first(ws: Workspace, user_id: int | None) -> list[dict]:
    """Read every record of one account, newest first and in batch order within a second."""
    directory = author_dir(ws, user_id)
    if not directory.is_dir():
        return []
    records = [r for r in (_read(path) for path in directory.glob("*.json")) if r is not None]
    records.sort(key=_order, reverse=True)
    return records


def _order(record: dict) -> tuple[str, int]:
    """Return the key that sorts records by date, and by batch position within a second."""
    return str(record.get("created_at") or ""), (record.get("job") or {}).get("index") or 0


def _matches(
    record: dict, concept: str | None, item_type: str | None, query: str | None
) -> bool:
    """Say whether a record is of this modality, practises this concept and holds this text."""
    if item_type and item_type_of(record) != item_type:
        return False
    if concept and concept not in concepts_of(record):
        return False
    return not query or query.lower() in _searchable(record)


def _read(path: Path) -> dict | None:
    """Read one record, or None when it is missing or unreadable — said once per file."""
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        _warn_once(path, str(exc))
        return None
    if not isinstance(record, dict):
        _warn_once(path, "no es un objeto JSON")
        return None
    return record


def _warn_once(path: Path, reason: str) -> None:
    """Warn about one unreadable file the first time it is met."""
    if path in _warned:
        return
    _warned.add(path)
    logger.warning(f"[generations] Se salta un ejercicio ilegible '{path}': {reason}")


def _searchable(record: dict) -> str:
    """Return one lowercase string holding everything a free-text query may match."""
    parts = [str(value) for value in item_of(record).values() if isinstance(value, str)]
    parts.extend(concepts_of(record))
    parts.append((record.get("commission") or {}).get("instructions") or "")
    return " ".join(parts).lower()


# THE RECORD ----------------------------------------------------------------------------


def item_of(record: dict) -> dict:
    """Return the exercise itself."""
    return (record.get("output") or {}).get("item") or {}


def item_type_of(record: dict) -> str:
    """Return the modality it was written in."""
    resolved = record.get("resolved") or {}
    commission = record.get("commission") or {}
    return resolved.get("item_type") or commission.get("item_type") or ""


def concepts_of(record: dict) -> list[str]:
    """Return the concepts it practises: the targets that ran, else the ones asked for."""
    resolved = record.get("resolved") or {}
    commission = record.get("commission") or {}
    return list(resolved.get("targets") or commission.get("concepts") or [])


def created_at(record: dict) -> float:
    """Return when it was written, as an epoch timestamp, or 0 when unreadable."""
    try:
        return datetime.fromisoformat(str(record.get("created_at")).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def author_dir(ws: Workspace, user_id: int | None) -> Path:
    """Return the directory one account's exercises live in; `None` is the orphaned one."""
    if user_id is None:
        return ws.generations_dir / ORPHANED
    return ws.generations_dir / f"{AUTHOR_PREFIX}{int(user_id)}"


def stamp(moment: datetime) -> str:
    """Render a moment as the compact UTC stamp an id starts with."""
    return _utc(moment).strftime("%Y%m%dT%H%M%SZ")


def iso(moment: datetime) -> str:
    """Render a moment as the UTC ISO string a record carries."""
    return _utc(moment).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc(moment: datetime) -> datetime:
    """Read a naive moment as UTC, and convert an aware one to it."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)
