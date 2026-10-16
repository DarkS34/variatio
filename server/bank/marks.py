"""What a teacher marks on the exercises of a subject's bank: who sees them, and the stars.

Neither is content of the bank: neither enters its hash nor touches its approval, and a
re-extraction must not lose them. So an exercise is named here by its CONTENT — a fingerprint
of its type and its folded statement, the very key the bank's builder tells two extractions
apart by, and its place among the exercises that repeat that statement (`keys`) — and never
by its id, which a re-extraction renumbers. Editing a statement moves its
marks to the new fingerprint (`routes/bank.patch`, which knows both). A mark whose exercise
is gone is not answered: they are read against the bank every time.

WHO SEES AN EXERCISE is the subject's, a file beside `.curriculum.json`
(`ws.bank_visibility_path`): `{key: {"level": "full"}}` or `{"level": "fields", "fields":
[...]}`, and hidden is no entry — every exercise is hidden until a teacher shows it (the
user's decision, 2026-10-14). The fields a teacher may show are the type's own but the
difficulty, which is always seen as the level; the statement always goes. An entry may name
`groups` (ids of the class's groups): then only their students see it; without it the whole
class does. A group deleted is taken out of every entry, and an entry left with none is
hidden again (`forget_group`). A FAVOURITE is one teacher's, a row (`bank_favourites`), and
changes nothing but a filter and the look of a row.
"""

import hashlib
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from variatio.core import json_io
from variatio.core.lexicon import fold
from variatio.core.workspace import Workspace
from variatio.loaders.exemplars_profile import ExemplarsProfile, ItemType

from .. import auth
from ..classroom import groups
from ..db.models import BankFavourite
from ..pipeline import storage

HIDDEN = "hidden"
FULL = "full"
FIELDS = "fields"
LEVELS = (HIDDEN, FULL, FIELDS)


def keys(profile: ExemplarsProfile, bank: dict[str, dict]) -> dict[str, str]:
    """Name every exercise of a bank by its content, the repeats of one statement apart.

    Two documents may hold the same exercise — an exam and its solutions —, and a mark set on
    one must not land on the other: the second of one statement is `key~2`, the third `key~3`,
    in the bank's order, which a re-extraction keeps (documents are read in the same order).
    An exercise with no statement has no key and takes no mark.
    """
    seen: dict[str, int] = {}
    named: dict[str, str] = {}
    for item_id, item in bank.items():
        key = fingerprint(profile, item)
        if key is None:
            continue
        seen[key] = seen.get(key, 0) + 1
        named[item_id] = key if seen[key] == 1 else f"{key}~{seen[key]}"
    return named


def fingerprint(profile: ExemplarsProfile, item: dict) -> str | None:
    """Name an exercise by its type and its folded statement; None when it has no statement."""
    try:
        item_type = profile.item_type_of(item)
        text = item_type.primary_text(item)
    except (KeyError, ValueError, TypeError):
        return None
    if not text.strip():
        return None
    identity = f"{item_type.key}::{fold(text).strip()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


# WHO SEES AN EXERCISE ----------------------------------------------------------------------


def showable_fields(item_type: ItemType) -> list[str]:
    """Return the fields a teacher may show of an exercise: all but the difficulty, the
    statement first."""
    difficulty = item_type.difficulty_field
    fields = [name for name in item_type.field_specs if name != difficulty]
    primary = item_type.primary_field
    return [primary, *(name for name in fields if name != primary)]


def visibility(ws: Workspace) -> dict[str, dict]:
    """Read who sees which exercise, keyed by content; an unreadable file shows nothing.

    An entry naming groups that names none is nobody's, and is left out like a hidden one.
    """
    data = storage.read_json(ws.bank_visibility_path)
    if not isinstance(data, dict):
        return {}
    return {
        key: entry
        for key, entry in data.items()
        if isinstance(entry, dict)
        and entry.get("level") in (FULL, FIELDS)
        and (_groups(entry) is None or _groups(entry))
    }


def shown(entry: dict | None, item_type: ItemType | None) -> dict | None:
    """Return what students see of one exercise, as the screens read it, or None if hidden.

    A field the type no longer declares is dropped, and the statement always stays. `groups`
    is None when the whole class sees it.
    """
    if not entry or item_type is None:
        return None
    groups = _groups(entry)
    if entry.get("level") == FULL:
        return {"level": FULL, "fields": showable_fields(item_type), "groups": groups}
    allowed = showable_fields(item_type)
    chosen = set(entry.get("fields") or [])
    fields = [name for name in allowed if name in chosen or name == item_type.primary_field]
    return {"level": FIELDS, "fields": fields, "groups": groups}


def seen_by(entry: dict | None, group_id: int | None) -> bool:
    """Whether a student of this group (None: of no group) sees an exercise so marked."""
    if not entry:
        return False
    groups = _groups(entry)
    return groups is None or (group_id is not None and group_id in groups)


def set_visibility(
    ws: Workspace,
    keys: list[str],
    level: str,
    fields: list[str] | None = None,
    groups: list[int] | None = None,
) -> None:
    """Show these exercises whole, show the chosen fields of them, or hide them.

    `groups` names the groups that see them; None is the whole class.
    """
    data = visibility(ws)
    scope = {"groups": sorted(set(groups))} if groups is not None else {}
    for key in keys:
        if level == HIDDEN:
            data.pop(key, None)
        elif level == FULL:
            data[key] = {"level": FULL, **scope}
        else:
            data[key] = {"level": FIELDS, "fields": list(fields or []), **scope}
    json_io.write_json(ws.bank_visibility_path, data)


def forget_group(ws: Workspace, group_id: int) -> None:
    """Take a deleted group out of every entry; one it alone saw is hidden again.

    Done when the group goes, and not left to the reading: an id may be given again (SQLite
    reuses the highest one), and a new group must not inherit what an old one saw.
    """
    data = visibility(ws)
    changed = False
    for key, entry in list(data.items()):
        groups = _groups(entry)
        if groups is None or group_id not in groups:
            continue
        changed = True
        rest = [group for group in groups if group != group_id]
        if rest:
            entry["groups"] = rest
        else:
            data.pop(key)
    if changed:
        json_io.write_json(ws.bank_visibility_path, data)


def _groups(entry: dict) -> list[int] | None:
    """Return the groups an entry is for, or None when it is for the whole class."""
    groups = entry.get("groups")
    if not isinstance(groups, list):
        return None
    return [group for group in groups if isinstance(group, int) and not isinstance(group, bool)]


# THE STARS ---------------------------------------------------------------------------------


def favourites(session: Session, workspace_id: int, user_id: int) -> frozenset[str]:
    """Return the exercises this teacher marked with the star in this subject."""
    return frozenset(
        session.scalars(
            select(BankFavourite.item_key).where(
                BankFavourite.workspace_id == workspace_id, BankFavourite.user_id == user_id
            )
        )
    )


def set_favourite(session: Session, workspace_id: int, user_id: int, key: str, on: bool) -> None:
    """Mark or unmark one exercise with this teacher's star; doing it twice changes nothing."""
    row = session.scalar(
        select(BankFavourite).where(
            BankFavourite.workspace_id == workspace_id,
            BankFavourite.user_id == user_id,
            BankFavourite.item_key == key,
        )
    )
    if on and row is None:
        session.add(BankFavourite(workspace_id=workspace_id, user_id=user_id, item_key=key))
    elif not on and row is not None:
        session.delete(row)
    session.flush()


# A STATEMENT REWRITTEN ---------------------------------------------------------------------


def move(ws: Workspace, session: Session, workspace_id: int, old: str, new: str) -> None:
    """Carry an exercise's marks to its new fingerprint, every teacher's stars included."""
    if old == new:
        return
    data = visibility(ws)
    if old in data:
        data[new] = data.pop(old)
        json_io.write_json(ws.bank_visibility_path, data)
    taken = set(
        session.scalars(
            select(BankFavourite.user_id).where(
                BankFavourite.workspace_id == workspace_id, BankFavourite.item_key == new
            )
        )
    )
    if taken:
        session.execute(
            delete(BankFavourite).where(
                BankFavourite.workspace_id == workspace_id,
                BankFavourite.item_key == old,
                BankFavourite.user_id.in_(taken),
            )
        )
    session.execute(
        update(BankFavourite)
        .where(BankFavourite.workspace_id == workspace_id, BankFavourite.item_key == old)
        .values(item_key=new)
    )
    session.flush()


class Shown(BaseModel):
    """What the class sees of an exercise: nothing, all of it, or the fields chosen.

    `groups` names the groups of the class that see it; absent, the whole class does.
    """

    level: Literal["hidden", "full", "fields"] = "hidden"
    fields: list[str] = []
    groups: list[int] | None = None


def checked_groups(db: Session, access: auth.Access, visibility: Shown | None) -> None:
    """Refuse groups that are not this class's, or a choice of groups that names none.

    Public because passing a generated exercise in (`consumers.generation`) chooses the groups
    too, before anything is written.
    """
    if visibility is None or visibility.groups is None or visibility.level == HIDDEN:
        return
    if not visibility.groups:
        raise HTTPException(422, "Elige al menos un grupo, o toda la clase.")
    known = {group.id for group in groups.all_of(db, access.workspace)}
    if any(group not in known for group in visibility.groups):
        raise HTTPException(404, "Ese grupo no existe en esta asignatura.")
