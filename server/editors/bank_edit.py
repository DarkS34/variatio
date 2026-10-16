"""Editing the exemplars bank: item fields and, above all, their concepts.

Tags can only ever name concepts that exist in the knowledge graph. The pipeline
already guarantees this on the machine side — the embedder only scores KG concepts
and the tagger filters the LLM's answer against the candidate list — so the only new
surface is manual editing, and it is validated here for the same reason.

Every exercise says where it comes from (`origin`, since 2026-10-14): collected from the
teacher's documents (`extracted`, `C###`), written by a teacher (`manual`, `M###`), or a
generated exercise passed into the bank (`generated`, `G###`). The two added by somebody also
say who and when (`added_by`, an account id; `added_at`). An exercise written before the
field is read by its id: `G###` was promoted, anything else was collected.
"""

import re
import uuid
from datetime import datetime, timezone

from variatio import config
from variatio.core import json_io
from variatio.runtime.tagger import TRACE_KEY
from variatio.core.workspace import Workspace
from variatio.loaders.exemplars_profile import ITEM_TYPE_KEY, ExemplarsProfile
from variatio.loaders.knowledge_graph import KnowledgeGraph

from .. import approvals, bank_marks, storage
from ..core import contexts

ARTIFACT = approvals.EXEMPLARS_BANK

# Not part of the content schema, but part of every item on disk.
META_FIELDS = (
    "source",
    "concepts",
    "primary_concept",
    ITEM_TYPE_KEY,
    TRACE_KEY,
    "origin",
    "added_by",
    "added_at",
)

# Where an exercise of the bank comes from.
EXTRACTED = "extracted"
MANUAL = "manual"
GENERATED = "generated"
ORIGINS = (EXTRACTED, MANUAL, GENERATED)

# The id prefix of what somebody adds; what the extraction collects is `C###`.
ID_PREFIX = {MANUAL: "M", GENERATED: "G"}

PROMOTED_ID_RE = re.compile(r"^G(\d+)$")
MANUAL_ID_RE = re.compile(r"^M(\d+)$")


def _primary_text(profile: ExemplarsProfile, item: dict) -> str:
    """Read an item's primary field, empty when the profile can no longer place it.

    The listing sorts and searches over items a stale profile may not recognise, so this
    must never raise.
    """
    try:
        return profile.primary_text(item)
    except ValueError:
        return ""


class BankError(ValueError):
    """A bank edit that the caller can be told about, in Spanish."""


def origin_of(item_id: str, item: dict) -> str:
    """Say where one exercise comes from, reading an older one by its id."""
    origin = item.get("origin")
    if origin in ORIGINS:
        return origin
    if PROMOTED_ID_RE.match(item_id):
        return GENERATED
    if MANUAL_ID_RE.match(item_id):
        return MANUAL
    return EXTRACTED


def listing(
    ws: Workspace,
    concept: str | None = None,
    untagged: bool | None = None,
    query: str | None = None,
    source: str | None = None,
    item_type: str | None = None,
    difficulty: str | None = None,
    order: str = "id",
    page: int = 1,
    page_size: int = 50,
    origin: str | None = None,
    favourites: frozenset[str] = frozenset(),
    visible_only: bool = False,
    favourites_only: bool = False,
) -> dict:
    """Return one page of the bank, filtered and sorted, with the totals drawn around it.

    `sources` names the documents the exercises were collected from, and only those: what a
    teacher added comes from no document, and is filtered by `origin` instead. Each exercise
    of the page says what the students see of it (`visibility`) and whether it is one of
    `favourites`, the asking teacher's stars; `marks` counts both over the whole bank.
    """
    bank = _load_bank(ws)
    profile = _profile(ws)
    shown = bank_marks.visibility(ws)
    named = bank_marks.keys(profile, bank)

    rows = [
        {
            "id": item_id,
            **item,
            "origin": origin_of(item_id, item),
            "key": named.get(item_id),
        }
        for item_id, item in bank.items()
    ]
    counts = {name: sum(1 for row in rows if row["origin"] == name) for name in ORIGINS}
    sources = sorted(
        {str(row["source"]) for row in rows if row.get("source") and row["origin"] == EXTRACTED}
    )
    marks = {
        "visible": sum(1 for row in rows if row["key"] in shown),
        "favourites": sum(1 for row in rows if row["key"] in favourites),
        # What a re-extraction keeps only if it reads the same statement again.
        "extracted": sum(
            1
            for row in rows
            if row["origin"] == EXTRACTED and (row["key"] in shown or row["key"] in favourites)
        ),
    }
    rows = [
        r
        for r in rows
        if _matches(r, profile, concept, untagged, query, source, item_type, difficulty)
        and (not origin or r["origin"] == origin)
        and (not visible_only or r["key"] in shown)
        and (not favourites_only or r["key"] in favourites)
    ]
    _sort(rows, order, profile)

    total = len(rows)
    start = max(0, (page - 1) * page_size)
    window = [
        {
            **row,
            "visibility": bank_marks.shown(shown.get(row["key"]), _type_of(profile, row)),
            "favourite": row["key"] in favourites,
        }
        for row in rows[start : start + page_size]
    ]

    all_items = list(bank.values())
    untagged_count = sum(1 for item in all_items if not item.get("concepts"))
    return {
        "items": window,
        "total": total,
        "page": page,
        "page_size": page_size,
        "item_types": _type_summaries(profile, all_items),
        "difficulties": _difficulty_summaries(profile, all_items),
        "default_type": profile.default_type,
        "sources": sources,
        "origins": counts,
        "marks": marks,
        "totals": {
            "items": len(all_items),
            "tagged": len(all_items) - untagged_count,
            "untagged": untagged_count,
        },
        "thresholds": {
            "similarity": config.EMBEDDER_SIMILARITY_THRESHOLD,
            "top_k": config.TAGGER_TOP_K_CANDIDATES,
        },
    }


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


def _type_of(profile: ExemplarsProfile, item: dict):
    """Return an exercise's type, or None when the profile cannot place it."""
    try:
        return profile.item_type_of(item)
    except ValueError:
        return None


def _matches(
    row: dict,
    profile: ExemplarsProfile,
    concept: str | None,
    untagged: bool | None,
    query: str | None,
    source: str | None,
    item_type: str | None,
    difficulty: str | None = None,
) -> bool:
    """Whether one row survives every filter the listing was given.

    `untagged` is three-valued: `None` asks nothing, `True` keeps only the items with no
    concepts and `False` only the tagged ones.
    """
    if concept and concept not in (row.get("concepts") or []):
        return False
    if untagged is True and row.get("concepts"):
        return False
    if untagged is False and not row.get("concepts"):
        return False
    if source and row.get("source") != source:
        return False
    if item_type and profile.type_key_of_safe(row) != item_type:
        return False
    if difficulty and profile.difficulty_of(row) != difficulty:
        return False
    if query:
        needle = query.lower()
        text = _primary_text(profile, row).lower()
        if needle not in text and needle not in row["id"].lower():
            return False
    return True


def _sort(rows: list[dict], order: str, profile: ExemplarsProfile) -> None:
    """Sort the rows in place by id, by review priority, by difficulty, or newest first."""
    if order == "suspicion":
        rows.sort(key=lambda r: (_suspicion(r), r["id"]))
    elif order == "difficulty":
        # Easiest first, and the rank is the position in the MODALITY's own ladder rather
        # than in a table here — a profile whose rungs somebody renamed by hand still sorts
        # the way its own declaration reads. An item with no readable difficulty ranks last
        # instead of passing for the entry level.
        rows.sort(key=lambda r: (profile.difficulty_rank_of(r), r["id"]))
    elif order == "recent":
        # Ids are C001, C002… in extraction order, so "the last thing written" is the tail of
        # that list. No screen asks for it: it stays because this listing is an API and
        # "newest first" is a real order, and `tests/server/test_bank_recent_order.py` is
        # what keeps it from being swept up as dead — as with the `concept` filter.
        rows.sort(key=lambda r: r["id"], reverse=True)
    else:
        rows.sort(key=lambda r: r["id"])


def _suspicion(item: dict) -> tuple[int, float]:
    """Rank an item for review: untagged first, then narrow calls, then everything else.

    An item with no concepts is dead weight — it can never be picked as a few-shot
    example — and a decision won by a hair is the one most worth a human glance.
    """
    trace = item.get(TRACE_KEY) or {}
    candidates = trace.get("candidates") or []
    if not item.get("concepts"):
        return (0, 0.0)
    if len(candidates) >= 2:
        margin = float(candidates[0][1]) - float(candidates[1][1])
        return (1, margin)
    return (2, 1.0)


def _type_summaries(profile: ExemplarsProfile, all_items: list[dict]) -> list[dict]:
    """Describe every modality the profile declares, with how many items carry it.

    Declared by the profile and not gathered from the bank, so the caller can tell a
    modality nobody has written from one the profile has never heard of.
    """
    return [
        {
            "key": key,
            "label": t.label,
            "description": t.description,
            "primary_field": t.primary_field,
            "embed_fields": list(t.embed_fields),
            "fields": list(t.field_specs),
            # Named rather than left for the client to recognise: the field's name is the
            # workspace's PROMPT language's, and a table drawing a column should not have to
            # know which language a profile was built in.
            "difficulty_field": t.difficulty_field,
            "difficulty_levels": t.difficulty_levels,
            "count": sum(1 for i in all_items if profile.type_key_of_safe(i) == key),
        }
        for key, t in profile.item_types.items()
    ]


def _difficulty_summaries(profile: ExemplarsProfile, all_items: list[dict]) -> list[dict]:
    """Every rung the profile declares, with how many items of the whole bank sit on it.

    Declared and not gathered, exactly as the modalities are: a rung nobody has written yet
    is still a rung one may filter by, and it says "0" instead of not being offered.
    """
    counts: dict[str, int] = {level: 0 for level in profile.declared_difficulties()}
    for item in all_items:
        level = profile.difficulty_of(item)
        if level in counts:
            counts[level] += 1
    return [{"value": level, "count": count} for level, count in counts.items()]


def coverage(ws: Workspace) -> dict:
    """Count the exemplars per concept — that is, say which concepts generate zero-shot."""
    bank = _load_bank(ws)
    graph = _graph(ws)
    counts: dict[str, int] = dict.fromkeys(graph.taggable_concepts, 0)
    for item in bank.values():
        for concept in item.get("concepts") or []:
            if concept in counts:
                counts[concept] += 1
    without = sorted(c for c, n in counts.items() if n == 0)
    return {
        "counts": counts,
        "covered": len(counts) - len(without),
        "total": len(counts),
        "without_exemplars": without,
    }


def patch_item(ws: Workspace, item_id: str, fields: dict) -> dict:
    """Edit one item's fields, validated against the modality the result declares."""
    bank = _load_bank(ws)
    if item_id not in bank:
        raise BankError(f"El ítem '{item_id}' no existe")

    profile = _profile(ws)
    merged = {**bank[item_id], **fields}
    try:
        item_type = profile.item_type_of(merged)
    except ValueError as exc:
        raise BankError(str(exc)) from exc

    schema_fields = set(item_type.field_specs)
    unknown = [k for k in fields if k not in schema_fields and k not in META_FIELDS]
    if unknown:
        raise BankError(
            f"Campos desconocidos para la modalidad '{item_type.key}': {unknown}"
        )

    # Validate exactly what the schema declares: the extra keys (source, tags, trace) are
    # ours, and the model would reject or drop them.
    candidate = {k: v for k, v in merged.items() if k in schema_fields}
    try:
        item_type.content_item(**candidate)
    except Exception as exc:  # noqa: BLE001 - pydantic errors are the message
        raise BankError(f"El ítem no cumple el esquema: {exc}") from exc

    # Changing the modality rewrites the item's anatomy: the previous type's fields are
    # dropped rather than left behind, where the next reader would take them for content.
    meta = {k: v for k, v in merged.items() if k in META_FIELDS and k != ITEM_TYPE_KEY}
    updated = {ITEM_TYPE_KEY: item_type.key, **candidate, **meta}

    bank[item_id] = updated
    result = _persist(ws, bank, f"ítem '{item_id}' editado")
    result["item"] = {"id": item_id, **updated}
    return result


def set_concepts(
    ws: Workspace, item_id: str, concepts: list[str], primary_concept: str | None
) -> dict:
    """Retag one item by hand, refusing any concept the graph does not hold as taggable.

    The trace is marked `manual`, so a later reader can tell a person's decision from the
    tagger's.
    """
    bank = _load_bank(ws)
    if item_id not in bank:
        raise BankError(f"El ítem '{item_id}' no existe")

    taggable = set(_graph(ws).taggable_concepts)
    invalid = [c for c in concepts if c not in taggable]
    if invalid:
        raise BankError(f"Conceptos que no están en el grafo: {invalid}")
    if primary_concept and primary_concept not in concepts:
        raise BankError("El concepto principal debe estar entre los conceptos asignados")
    if concepts and not primary_concept:
        primary_concept = concepts[0]

    item = dict(bank[item_id])
    item["concepts"] = list(concepts)
    item["primary_concept"] = primary_concept if concepts else None
    trace = dict(item.get(TRACE_KEY) or {})
    trace["method"] = "manual"
    item[TRACE_KEY] = trace
    bank[item_id] = item

    result = _persist(ws, bank, f"conceptos de '{item_id}' editados")
    result["item"] = {"id": item_id, **item}
    return result


def has_item(ws: Workspace, item_id: str) -> bool:
    """Whether the bank holds this item; False rather than an error when there is no bank."""
    return item_id in item_ids(ws)


def item_ids(ws: Workspace) -> frozenset[str]:
    """Return the ids the bank holds, none when there is no bank."""
    try:
        return frozenset(_load_bank(ws))
    except BankError:
        return frozenset()


def add_item(
    ws: Workspace,
    fields: dict,
    item_type_key: str | None,
    concepts: list[str],
    primary_concept: str | None = None,
    *,
    origin: str = GENERATED,
    added_by: int | None = None,
    added_at: str | None = None,
) -> dict:
    """Add one exercise somebody wrote or passed in, under a fresh id of its origin.

    A teacher's (`manual`, `M###`) is that person's decision, so a concept the graph does not
    hold as a label is refused, as in `set_concepts`. A generated exercise passed into the
    bank (`generated`, `G###`) carries a machine's concepts, so one the graph does not hold is
    dropped instead. With no concepts the exercise waits for the tagger (`tag_item`).
    """
    if origin not in ID_PREFIX:
        raise BankError(f"Origen desconocido: «{origin}»")
    bank = _load_bank(ws)
    profile = _profile(ws)
    try:
        item_type = profile.item_type(item_type_key or None)
    except ValueError as exc:
        raise BankError(str(exc)) from exc

    schema_fields = set(item_type.field_specs)
    candidate = {k: v for k, v in fields.items() if k in schema_fields}
    try:
        item_type.content_item(**candidate)
    except Exception as exc:  # noqa: BLE001 - pydantic errors are the message
        raise BankError(f"El ítem no cumple el esquema: {exc}") from exc

    taggable = set(_graph(ws).taggable_concepts)
    if origin == MANUAL:
        invalid = [c for c in concepts if c not in taggable]
        if invalid:
            raise BankError(f"Conceptos que no están en el grafo: {invalid}")
        if primary_concept and primary_concept not in concepts:
            raise BankError("El concepto principal debe estar entre los conceptos asignados")
    kept = [c for c in concepts if c in taggable]
    primary = primary_concept if primary_concept in kept else (kept[0] if kept else None)

    item_id = _next_id(bank, ID_PREFIX[origin])
    item = {
        ITEM_TYPE_KEY: item_type.key,
        **candidate,
        "origin": origin,
        "added_by": added_by,
        "added_at": added_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "concepts": kept,
        "primary_concept": primary,
    }
    if kept:
        item[TRACE_KEY] = {"method": "manual" if origin == MANUAL else "promoted"}
    bank[item_id] = item

    note = (
        f"ejercicio '{item_id}' añadido a mano"
        if origin == MANUAL
        else f"variante promovida como '{item_id}'"
    )
    result = _persist(ws, bank, note)
    result["item"] = {"id": item_id, **item}
    return result


def apply_tags(ws: Workspace, annotations: dict[str, dict]) -> dict:
    """Write the tagger's concepts onto these exercises of the bank as it is NOW.

    Only the concepts, the primary concept and the trace of each one: the bank may have moved
    while they were being tagged — a teacher goes on adding — and writing back the whole bank
    the tagger read would lose what came in meanwhile. An exercise deleted in between is
    skipped.
    """
    bank = _load_bank(ws)
    written = [item_id for item_id in annotations if item_id in bank]
    for item_id in written:
        annotation = annotations[item_id]
        bank[item_id] = {
            **bank[item_id],
            "concepts": list(annotation.get("concepts") or []),
            "primary_concept": annotation.get("primary_concept"),
            TRACE_KEY: annotation.get(TRACE_KEY) or {"method": "auto"},
        }
    if not written:
        return {"written": [], "hash": storage.sha256_of(ws.exemplars_bank_path)}
    result = _persist(ws, bank, f"conceptos de {', '.join(written)} etiquetados")
    result["written"] = written
    return result


def key_of(ws: Workspace, item_id: str) -> str | None:
    """Return the key marks name this exercise by, or None when it is not there."""
    return bank_marks.keys(_profile(ws), _load_bank(ws)).get(item_id)


def seed(ws: Workspace) -> tuple[dict[str, dict], dict[str, dict]]:
    """Split what a person added to the bank into what a re-extraction keeps and puts aside.

    A teacher's exercises and the generated ones passed in come from no document, so reading
    the documents again cannot bring them back (the user's decision, 2026-10-14: what was
    added survives). The ones that still fit the types of exercise are kept, ids and tags
    included; one that no longer does is put aside instead of lost.
    """
    try:
        bank = storage.read_json(ws.exemplars_bank_path) or {}
        profile = _profile(ws)
    except BankError:
        return {}, {}
    kept: dict[str, dict] = {}
    aside: dict[str, dict] = {}
    for item_id, item in bank.items():
        if origin_of(item_id, item) == EXTRACTED:
            continue
        try:
            item_type = profile.item_type_of(item)
            item_type.content_item(**{k: v for k, v in item.items() if k in item_type.field_specs})
        except Exception:  # noqa: BLE001 - whatever no longer validates is put aside
            aside[item_id] = item
            continue
        kept[item_id] = item
    return kept, aside


def aside(ws: Workspace) -> dict[str, dict]:
    """Return the exercises put aside by a re-extraction, keyed by their place here."""
    data = storage.read_json(ws.bank_set_aside_path)
    return data if isinstance(data, dict) else {}


def put_aside(ws: Workspace, items: dict[str, dict]) -> None:
    """Put these exercises aside, each with the id it had and when it left the bank."""
    data = aside(ws)
    moment = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for item_id, item in items.items():
        data[uuid.uuid4().hex[:12]] = {"item": item, "id": item_id, "at": moment}
    json_io.write_json(ws.bank_set_aside_path, data)


def take_aside(ws: Workspace, key: str) -> dict | None:
    """Remove one exercise from the ones put aside, and return it; None when it is not there."""
    data = aside(ws)
    entry = data.pop(key, None)
    if entry is not None:
        json_io.write_json(ws.bank_set_aside_path, data)
    return entry


def _profile(ws: Workspace) -> ExemplarsProfile:
    """Load the profile that wins. Raises BankError when there is none."""
    path = approvals.current_path(ws, approvals.EXEMPLARS_PROFILE)
    if path is None:
        raise BankError("Falta el perfil de ejemplares")
    return ExemplarsProfile(path)


def _graph(ws: Workspace) -> KnowledgeGraph:
    """Load the graph that wins. Raises BankError when there is none."""
    path = approvals.current_path(ws, approvals.KNOWLEDGE_GRAPH)
    if path is None:
        raise BankError("Falta el grafo de conocimiento")
    return KnowledgeGraph(str(path))


def _next_id(bank: dict, prefix: str) -> str:
    """Mint the next id of a prefix (`M###`, `G###`), one past its highest in the bank."""
    pattern = re.compile(rf"^{prefix}(\d+)$")
    highest = max((int(m.group(1)) for k in bank if (m := pattern.match(k))), default=0)
    return f"{prefix}{highest + 1:03d}"


def delete_item(ws: Workspace, item_id: str) -> dict:
    """Remove one item from the bank. Raises BankError when it is not there."""
    bank = _load_bank(ws)
    if item_id not in bank:
        raise BankError(f"El ítem '{item_id}' no existe")
    bank.pop(item_id)
    return _persist(ws, bank, f"ítem '{item_id}' eliminado")


def _load_bank(ws: Workspace) -> dict:
    """Read the bank. Raises BankError when the workspace has none yet.

    While a build runs this is the bank being WRITTEN and not the one it is going to
    replace: the live panel polls this listing to show what is coming out, and a
    re-extraction discards everything already on disk. That file exists for exactly as long
    as the build does, so outside one there is nothing to prefer.
    """
    bank = storage.read_json(ws.exemplars_bank_building_path)
    if bank is None:
        bank = storage.read_json(ws.exemplars_bank_path)
    if bank is None:
        raise BankError("Todavía no hay banco de ejemplos")
    return bank


def _persist(ws: Workspace, bank: dict, note: str) -> dict:
    """Write the bank, keep it closed if it was, and drop the cached context.

    A CLOSED BANK STAYS CLOSED (the user's decision, 2026-10-14): an exercise edited, tagged,
    added or deleted is sealed again, as a retag is (`handle_tag`), instead of sending the
    subject back to its construction — which closed the doors of a whole class for an
    erratum. Only a bank closed behind closed types and syllabus, and stale for nothing; a
    draft stays a draft, and editing the types still reopens everything after them.

    Refused while a build is writing one: what `_load_bank` reads then is the bank being
    made, and saving it here would put half a build in place of the artifact — and would be
    thrown away by the promotion regardless.
    """
    if ws.exemplars_bank_building_path.is_file():
        raise BankError(
            "El banco se está reconstruyendo: espera a que termine para editarlo"
        )
    review = approvals.Approvals(ws)
    closed = review.state(ARTIFACT)["status"] == "approved" and review.gate_open(ARTIFACT)
    storage.write_json(ws.exemplars_bank_path, bank, ws=ws, artifact=ARTIFACT)
    if closed:
        review.approve(ARTIFACT)
    else:
        review.invalidate(ARTIFACT)
    contexts.invalidate(ws.slug, note)
    return {"hash": storage.sha256_of(ws.exemplars_bank_path)}
