"""What a generated variant is put through before it is accepted.

`run` collects every signal and decides. A FLAG is reported to whoever reviews the item;
only a REASON forces another attempt — which is why the tagger's disagreement is flagged
and never retried on: it is an opinion about the index, not a defect in the item.
"""

import numpy as np
from loguru import logger
from pydantic import BaseModel

from . import config
from .concept_tagger import TRACE_KEY, ConceptTagger
from .core.lexicon import mentions
from .embedder import Embedder
from .instance.exemplars_profile import ItemType

MIN_PRIMARY_CHARS = 20


def content_floor(item: BaseModel, item_type: ItemType) -> str | None:
    """Return why the item is too empty to be worth keeping, or None.

    A required field explicitly typed as nullable does not count as missing.
    """
    data = item.model_dump(mode="json")
    primary = data.get(item_type.primary_field)
    if not isinstance(primary, str) or len(primary.strip()) < MIN_PRIMARY_CHARS:
        return f"el campo principal «{item_type.primary_field}» está vacío o es demasiado corto"
    schema = item_type.stripped_schema()
    properties = schema.get("properties", {})
    missing = [
        name
        for name in schema.get("required", [])
        if data.get(name) in (None, "") and not _nullable(properties.get(name, {}))
    ]
    if missing:
        return f"campo(s) obligatorio(s) sin contenido: {', '.join(missing)}"
    return None


def _nullable(spec: dict) -> bool:
    """True when the field's schema admits null."""
    return any(option.get("type") == "null" for option in spec.get("anyOf", []))


def _texts(item: BaseModel) -> list[str]:
    """Every string-valued field of the item."""
    return [value for value in item.model_dump(mode="json").values() if isinstance(value, str)]


def forbidden_mentions(item: BaseModel, forbidden: list[str]) -> list[str]:
    """Return the not-yet-taught concepts the item actually mentions."""
    texts = _texts(item)
    return [c for c in forbidden if any(mentions(text, c) for text in texts)]


def nearest(
    embedder: Embedder, text: str, others: list[tuple[str, str]]
) -> tuple[str, float] | None:
    """Return the label of whichever of `others` is closest to `text`, with its score."""
    if not others:
        return None
    vector = embedder.embed_document(text)
    best_label, best_score = None, -1.0
    for label, other in others:
        score = float(np.dot(vector, embedder.embed_document(other)))
        if score > best_score:
            best_label, best_score = label, score
    return best_label, round(best_score, 4)


def tagger_roundtrip(tagger: ConceptTagger, text: str, targets: list[str]) -> dict:
    """Tag the generated item afresh and report whether it lands on the targets."""
    annotation = tagger.tag(text)
    primary = annotation.get("primary_concept")
    tagged = list(annotation.get("concepts") or [])
    return {
        "primary": primary,
        "concepts": tagged,
        "method": (annotation.get(TRACE_KEY) or {}).get("method"),
        "on_target": primary in targets if primary else False,
        "targets_found": [c for c in targets if c in tagged],
    }


def run(
    item: BaseModel,
    item_type: ItemType,
    *,
    targets: list[str],
    forbidden: list[str],
    embedder: Embedder,
    tagger: ConceptTagger | None,
    few_shot: list[tuple[str, dict]],
    batch: list[BaseModel],
) -> dict:
    """Run every check over one variant and return the collected verdict.

    Similarity is measured against the few-shot exemplars AND the batch produced so far,
    so a run that repeats itself is caught as well as one that copies its examples.
    """
    text = item_type.embed_text(item.model_dump(mode="json"))
    checks: dict = {}

    hits = forbidden_mentions(item, forbidden)
    checks["forbidden"] = hits

    others = [(ex_id, item_type.embed_text(ex)) for ex_id, ex in few_shot]
    others += [
        (f"lote {i + 1}", item_type.embed_text(previous.model_dump(mode="json")))
        for i, previous in enumerate(batch)
    ]
    close = nearest(embedder, text, others)
    checks["similarity"] = (
        {"to": close[0], "score": close[1], "high": close[1] >= config.CHECK_SIMILARITY_THRESHOLD}
        if close
        else None
    )

    if tagger is not None:
        checks["tagger"] = tagger_roundtrip(tagger, text, targets)

    reasons = []
    if hits:
        reasons.append(f"menciona lo no impartido: {', '.join(hits)}")
    if checks["similarity"] and checks["similarity"]["high"]:
        reasons.append(f"muy parecida a {close[0]} ({close[1]:.2f})")
    flags = list(reasons)
    # Whether a target is among the tags AT ALL, never whether it was made primary. Which
    # of several targets an item practises is the generator's business — the prompt asks
    # for one or two out of the set — so `on_target`, which this read until 2026-09-02,
    # flagged a disagreement about ranking as if it were a miss.
    if tagger is not None and targets and not checks["tagger"]["targets_found"]:
        missed = f"el etiquetador no la reconoce como {' / '.join(targets)}"
        seen = checks["tagger"]["primary"]
        flags.append(f"{missed}; la etiqueta como «{seen}»" if seen else missed)
    checks["flags"] = flags
    checks["reasons"] = reasons
    checks["verdict"] = "retry" if reasons else "accept"
    if flags:
        logger.warning(f"Variant flagged: {'; '.join(flags)}")
    return checks


def needs_retry(checks: dict | None) -> bool:
    """True when the checks asked for another attempt."""
    return bool(checks) and checks.get("verdict") == "retry"


def correction_text(checks: dict | None) -> str:
    """Render the retry reasons as the correction block the next prompt carries."""
    return "\n".join(f"- {reason}" for reason in (checks or {}).get("reasons") or [])
