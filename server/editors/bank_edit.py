"""Editing the exemplars bank: item fields and, above all, their concepts.

Tags can only ever name concepts that exist in the knowledge graph. The pipeline
already guarantees this on the machine side — the embedder only scores KG concepts
and the tagger filters the LLM's answer against the candidate list — so the only new
surface is manual editing, and it is validated here for the same reason.
"""

from variant_generator import config
from variant_generator.concept_tagger import TRACE_KEY
from variant_generator.content_profile import ITEM_TYPE_KEY, ContentProfile
from variant_generator.knowledge_graph import KnowledgeGraph

from .. import deps, review, storage

ARTIFACT = review.EXEMPLARS_BANK

# Not part of the content schema, but part of every item on disk.
META_FIELDS = ("source", "concepts", "primary_concept", ITEM_TYPE_KEY, TRACE_KEY)


# The listing sorts and searches over items the profile may no longer be able to place —
# exactly the state a stale bank is in — so reading the primary text must never raise.
def _primary_text(profile: ContentProfile, item: dict) -> str:
    try:
        return profile.primary_text(item)
    except ValueError:
        return ""


class BankError(ValueError):
    pass


def _load_bank() -> dict:
    bank = storage.read_json(config.EXEMPLARS_BANK_PATH)
    if bank is None:
        raise BankError("Todavía no hay banco de ejemplos")
    return bank


def _profile() -> ContentProfile:
    path = review.current_path(review.CONTENT_PROFILE)
    if path is None:
        raise BankError("Falta el perfil de contenido")
    return ContentProfile(path)


def _graph() -> KnowledgeGraph:
    path = review.current_path(review.KNOWLEDGE_GRAPH)
    if path is None:
        raise BankError("Falta el grafo de conocimiento")
    return KnowledgeGraph(str(path))


def _suspicion(item: dict) -> tuple[int, float]:
    """Rank for review: untagged first, then narrow calls, then everything else.

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


def listing(
    concept: str | None = None,
    untagged: bool | None = None,
    query: str | None = None,
    source: str | None = None,
    item_type: str | None = None,
    order: str = "suspicion",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    bank = _load_bank()
    profile = _profile()

    rows = [{"id": item_id, **item} for item_id, item in bank.items()]

    if concept:
        rows = [r for r in rows if concept in (r.get("concepts") or [])]
    if untagged is True:
        rows = [r for r in rows if not r.get("concepts")]
    elif untagged is False:
        rows = [r for r in rows if r.get("concepts")]
    if source:
        rows = [r for r in rows if r.get("source") == source]
    if item_type:
        rows = [r for r in rows if r.get(ITEM_TYPE_KEY) == item_type]
    if query:
        needle = query.lower()
        rows = [
            r
            for r in rows
            if needle in _primary_text(profile, r).lower() or needle in r["id"].lower()
        ]

    if order == "suspicion":
        rows.sort(key=lambda r: (_suspicion(r), r["id"]))
    else:
        rows.sort(key=lambda r: r["id"])

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
        "item_types": [
            {
                "key": key,
                "label": t.label,
                "description": t.description,
                "primary_field": t.primary_field,
                "embed_fields": list(t.embed_fields),
                "fields": list(t.field_specs),
                "count": sum(
                    1 for i in all_items if profile.type_key_of_safe(i) == key
                ),
            }
            for key, t in profile.item_types.items()
        ],
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


def coverage() -> dict:
    """Which KG concepts have at least one exemplar — i.e. which ones generate zero-shot."""
    bank = _load_bank()
    graph = _graph()
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


def _persist(bank: dict, note: str) -> dict:
    storage.write_json(config.EXEMPLARS_BANK_PATH, bank, artifact=ARTIFACT)
    review.ReviewState().invalidate(ARTIFACT)
    deps.invalidate(note)
    return {"hash": storage.sha256_of(config.EXEMPLARS_BANK_PATH)}


def patch_item(item_id: str, fields: dict) -> dict:
    bank = _load_bank()
    if item_id not in bank:
        raise BankError(f"El ítem '{item_id}' no existe")

    profile = _profile()
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

    # Validate exactly what the schema declares; the extra keys (source, tags, trace)
    # are ours and the model would reject or drop them.
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
    result = _persist(bank, f"ítem '{item_id}' editado")
    result["item"] = {"id": item_id, **updated}
    return result


def set_concepts(item_id: str, concepts: list[str], primary_concept: str | None) -> dict:
    bank = _load_bank()
    if item_id not in bank:
        raise BankError(f"El ítem '{item_id}' no existe")

    taggable = set(_graph().taggable_concepts)
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

    result = _persist(bank, f"conceptos de '{item_id}' editados")
    result["item"] = {"id": item_id, **item}
    return result


def delete_item(item_id: str) -> dict:
    bank = _load_bank()
    if item_id not in bank:
        raise BankError(f"El ítem '{item_id}' no existe")
    bank.pop(item_id)
    return _persist(bank, f"ítem '{item_id}' eliminado")
