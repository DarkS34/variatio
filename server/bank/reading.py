"""The bank as the class reads it: what a teacher showed, cut to it, and whose eyes read it.

A student reads the exercises shown to their group or to the whole class, each with the
fields shown and nothing else of its content; a teacher reads every group's. The tutor and
the chat open a conversation on an exercise of the bank only through `readable`.
"""

from sqlalchemy.orm import Session as DbSession

from variatio.core.workspace import Workspace
from variatio.loaders.exemplars_profile import ITEM_TYPE_KEY

from .. import auth
from ..auth import queries
from ..db.models import VIEWER
from ..pipeline import storage
from . import marks as bank_marks
from .edit import (
    BankError,
    _difficulty_summaries,
    _graph,
    _matches,
    _profile,
    _type_of,
    _type_summaries,
)


def reader_of(db: DbSession, access: auth.Access) -> tuple[int | None, bool]:
    """Say whose eyes read the bank: a student's group, or every group for a teacher.

    Public because the functions that open a conversation on an exercise of the bank (the
    tutor, the chat) must refuse one this account cannot read.
    """
    if access.role != VIEWER:
        return None, True
    workspace_id = getattr(getattr(access, "workspace", None), "id", None)
    if not isinstance(workspace_id, int) or not isinstance(db, DbSession):
        return None, False
    group = queries.group_of(db, workspace_id, access.user.id)
    return (group.id if group is not None else None), False


def reading(
    ws: Workspace,
    group_id: int | None,
    every_group: bool = False,
    query: str | None = None,
    item_type: str | None = None,
    difficulty: str | None = None,
    concept: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Return one page of the bank as the class reads it: what a teacher showed, cut to it.

    Only the exercises shown to the reader's group (`group_id`, None for a student in no
    group) or to the whole class; `every_group` keeps the ones shown to any group, for a
    teacher. Each one carries the fields shown (`shown`, in the type's order, the statement
    first) and nothing else of its content, plus its type, its level and its concepts —
    never where it comes from, who added it or the tagger's trace. The types and the levels
    are counted over these alone, so the page says nothing of what is hidden.

    The finished bank, never the one a re-extraction is writing: a reader would watch it
    empty and fill again.
    """
    bank = storage.read_json(ws.exemplars_bank_path)
    if not isinstance(bank, dict):
        raise BankError("Todavía no hay banco de ejemplos")
    profile = _profile(ws)
    marks = bank_marks.visibility(ws)
    named = bank_marks.keys(profile, bank)

    rows = []
    for item_id, item in bank.items():
        entry = marks.get(named.get(item_id) or "")
        if not (entry and every_group) and not bank_marks.seen_by(entry, group_id):
            continue
        spec = _type_of(profile, item)
        shown = bank_marks.shown(entry, spec)
        if spec is None or shown is None:
            continue
        rows.append(_cut(item_id, item, spec, shown["fields"]))

    seen = list(rows)
    rows = [r for r in rows if _matches(r, profile, concept, None, query, None, item_type, difficulty)]
    total = len(rows)
    start = max(0, (page - 1) * page_size)
    return {
        "items": rows[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "item_types": [t for t in _type_summaries(profile, seen) if t["count"] > 0],
        "difficulties": _difficulty_summaries(profile, seen),
        "default_type": profile.default_type,
        "concepts": _concepts_read(ws, seen),
    }


def _concepts_read(ws: Workspace, rows: list[dict]) -> list[dict]:
    """Name the concepts the exercises read carry, each with its unit, in the syllabus' order.

    What the concept filter offers: a concept no exercise read carries would filter to
    nothing. A concept the graph no longer holds goes last, with no unit.
    """
    carried = {concept for row in rows for concept in row.get("concepts") or []}
    try:
        units = _graph(ws).concepts_by_domains
    except BankError:
        units = {}
    named = [
        {"name": concept, "unit": unit}
        for unit, concepts in units.items()
        for concept in concepts
        if concept in carried
    ]
    placed = {entry["name"] for entry in named}
    return named + [{"name": concept, "unit": None} for concept in sorted(carried - placed)]


def _cut(item_id: str, item: dict, spec, fields: list[str]) -> dict:
    """Keep of one exercise what the class sees: the fields shown, its level and concepts."""
    cut: dict = {"id": item_id, ITEM_TYPE_KEY: spec.key, "shown": list(fields)}
    for name in fields:
        if name in item:
            cut[name] = item[name]
    level = spec.difficulty_field
    if level and level in item:
        cut[level] = item[level]
    cut["concepts"] = list(item.get("concepts") or [])
    cut["primary_concept"] = item.get("primary_concept")
    return cut


def readable(ws: Workspace, item_id: str, group_id: int | None, every_group: bool = False) -> dict | None:
    """Return one exercise as the class reads it, or None when it is not shown to this reader."""
    bank = storage.read_json(ws.exemplars_bank_path)
    if not isinstance(bank, dict) or item_id not in bank:
        return None
    profile = _profile(ws)
    entry = bank_marks.visibility(ws).get(bank_marks.keys(profile, bank).get(item_id) or "")
    if not (entry and every_group) and not bank_marks.seen_by(entry, group_id):
        return None
    spec = _type_of(profile, bank[item_id])
    shown = bank_marks.shown(entry, spec)
    if spec is None or shown is None:
        return None
    return {**_cut(item_id, bank[item_id], spec, shown["fields"]), "key": bank_marks.keys(profile, bank)[item_id]}
