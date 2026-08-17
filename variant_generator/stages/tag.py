import json
from pathlib import Path

from loguru import logger

from ..concept_tagger import ConceptTagger
from .initialize import PipelineContext


def save_bank(bank: dict, path: str | Path) -> Path:
    """Atomic write: a cancelled or crashed run never leaves a half-written bank."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f"{target.suffix}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)
    tmp.replace(target)
    return target


def tag_bank(
    context: PipelineContext,
    ids: list[str] | None = None,
    path: str | Path | None = None,
) -> dict:
    """Assign knowledge-graph concepts to bank items and persist the result.

    `ids=None` tags only what is still untagged (resumable). Passing explicit ids
    re-tags those items even if they already carry concepts, which is what the
    review screen's "re-tag selected" does.
    """
    path = path or context.workspace.exemplars_bank_path

    pending = (
        [i for i in ids if i in context.exemplars_bank]
        if ids is not None
        else ConceptTagger.pending_ids(context.exemplars_bank)
    )

    if not pending:
        logger.info("El banco ya está anotado; no hay nada que etiquetar")
        context.apply_bank(context.exemplars_bank)
        return context.exemplars_bank

    # Persist as we go: tagging 150 items takes minutes, and a cancel halfway
    # through should keep every decision already made.
    working = dict(context.exemplars_bank)

    def checkpoint(item_id: str, item: dict) -> None:
        working[item_id] = item
        save_bank(working, path)

    try:
        annotated = context.tagger.tag_all(context.exemplars_bank, ids=pending, on_item=checkpoint)
    except BaseException:
        context.apply_bank(working)
        raise

    save_bank(annotated, path)
    logger.success(f"{len(pending)} ítem(s) etiquetados; banco guardado en {Path(path).name}")
    context.apply_bank(annotated)
    return annotated
