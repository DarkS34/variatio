from pathlib import Path

from loguru import logger

from ..concept_tagger import ConceptTagger
from ..core.json_io import write_json
from .initialize import PipelineContext


def save_bank(bank: dict, path: str | Path) -> Path:
    return write_json(path, bank)


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
        logger.info("The bank is already annotated; there is nothing to tag")
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
    logger.success(f"{len(pending)} item(s) tagged; bank saved to {Path(path).name}")
    context.apply_bank(annotated)
    return annotated
