"""Editing the exemplars bank: item fields and, above all, their concepts.

Tags can only ever name concepts that exist in the knowledge graph. The pipeline
already guarantees this on the machine side — the embedder only scores KG concepts
and the tagger filters the LLM's answer against the candidate list — so the only new
surface is manual editing, and it is validated here for the same reason.
"""

import re

from variatio import config
from variatio.concept_tagger import TRACE_KEY
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ITEM_TYPE_KEY, ExemplarsProfile
from variatio.instance.knowledge_graph import KnowledgeGraph

from .. import deps, review, storage

ARTIFACT = review.EXEMPLARS_BANK

# Not part of the content schema, but part of every item on disk.
META_FIELDS = ("source", "concepts", "primary_concept", ITEM_TYPE_KEY, TRACE_KEY)

PROMOTED_SOURCE = "Variante promovida"
PROMOTED_ID_RE = re.compile(r"^G(\d+)$")


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


def _profile(ws: Workspace) -> ExemplarsProfile:
    """Load the profile that wins. Raises BankError when there is none."""
    path = review.current_path(ws, review.EXEMPLARS_PROFILE)
    if path is None:
        raise BankError("Falta el perfil de ejemplares")
    return ExemplarsProfile(path)


def _graph(ws: Workspace) -> KnowledgeGraph:
    """Load the graph that wins. Raises BankError when there is none."""
    path = review.current_path(ws, review.KNOWLEDGE_GRAPH)
    if path is None:
        raise BankError("Falta el grafo de conocimiento")
    return KnowledgeGraph(str(path))


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
        # Ids are C001, C002… in extraction order, so «the last thing written» is the tail of
        # that list. No screen asks for it since the build's live feed was removed on
        # 2026-09-01; it stays because this listing is an API and «newest first» is a real
        # order, and `tests/server/test_bank_recent_order.py` is what keeps it from being
        # deleted as dead — the same arrangement the `concept` filter has.
        rows.sort(key=lambda r: r["id"], reverse=True)
    else:
        rows.sort(key=lambda r: r["id"])


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
    is still a rung one may filter by, and it says «0» instead of not being offered.
    """
    counts: dict[str, int] = {level: 0 for level in profile.declared_difficulties()}
    for item in all_items:
        level = profile.difficulty_of(item)
        if level in counts:
            counts[level] += 1
    return [{"value": level, "count": count} for level, count in counts.items()]


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
) -> dict:
    """Return one page of the bank, filtered and sorted, with the totals drawn around it."""
    bank = _load_bank(ws)
    profile = _profile(ws)

    rows = [{"id": item_id, **item} for item_id, item in bank.items()]
    rows = [
        r
        for r in rows
        if _matches(r, profile, concept, untagged, query, source, item_type, difficulty)
    ]
    _sort(rows, order, profile)

    total = len(rows)
    start = max(0, (page - 1) * page_size)
    window = rows[start : start + page_size]

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
        "sources": sorted({str(i.get("source")) for i in all_items if i.get("source")}),
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


def _persist(ws: Workspace, bank: dict, note: str) -> dict:
    """Write the bank, reopen its review and drop the cached context.

    Refused while a build is writing one: what `_load_bank` reads then is the bank being
    made, and saving it here would put half a build in place of the artifact — and would be
    thrown away by the promotion regardless.
    """
    if ws.exemplars_bank_building_path.is_file():
        raise BankError(
            "El banco se está reconstruyendo: espera a que termine para editarlo"
        )
    storage.write_json(ws.exemplars_bank_path, bank, ws=ws, artifact=ARTIFACT)
    review.ReviewState(ws).invalidate(ARTIFACT)
    deps.invalidate(ws.slug, note)
    return {"hash": storage.sha256_of(ws.exemplars_bank_path)}


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
    try:
        return item_id in _load_bank(ws)
    except BankError:
        return False


def add_item(
    ws: Workspace,
    fields: dict,
    item_type_key: str | None,
    concepts: list[str],
    primary_concept: str | None = None,
) -> dict:
    """Promote a generated variant into the bank under a fresh `G###` id.

    Unlike `set_concepts`, a concept the graph does not hold is dropped rather than
    refused: what is being promoted is a machine's answer, not somebody's decision.
    """
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
    kept = [c for c in concepts if c in taggable]
    primary = primary_concept if primary_concept in kept else (kept[0] if kept else None)

    item_id = _next_promoted_id(bank)
    item = {
        ITEM_TYPE_KEY: item_type.key,
        **candidate,
        "source": PROMOTED_SOURCE,
        "concepts": kept,
        "primary_concept": primary,
        TRACE_KEY: {"method": "promoted"},
    }
    bank[item_id] = item

    result = _persist(ws, bank, f"variante promovida como '{item_id}'")
    result["item"] = {"id": item_id, **item}
    return result


def _next_promoted_id(bank: dict) -> str:
    """Mint the next `G###` id, one past the highest promoted item already in the bank."""
    highest = max(
        (int(m.group(1)) for k in bank if (m := PROMOTED_ID_RE.match(k))),
        default=0,
    )
    return f"G{highest + 1:03d}"


def delete_item(ws: Workspace, item_id: str) -> dict:
    """Remove one item from the bank. Raises BankError when it is not there."""
    bank = _load_bank(ws)
    if item_id not in bank:
        raise BankError(f"El ítem '{item_id}' no existe")
    bank.pop(item_id)
    return _persist(ws, bank, f"ítem '{item_id}' eliminado")
