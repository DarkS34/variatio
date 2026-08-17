"""Arm 2 — the bank of the subject and a normal RAG. No graph anywhere.

This is the honest baseline: what a competent engineer builds with the same exercise
bank and none of this TFM. The `naive → rag` step measures what having a bank is worth;
the `rag → system` step measures what the GRAPH is worth, and that second one is the
contribution being defended.

Same local model as the system arm (`CONTENT_GENERATION_LLM`), the same number of examples
(`EVAL_RAG_TOP_K`) and the same reasoning mode (`commission.think`, drawn per session), so
neither the model, nor the prompt budget, nor whether it deliberated is a loose variable
between them.
"""

import time

from loguru import logger

from .. import config, inference, progress
from ..content_generator import build_few_shot_block, parse_item
from ..prompts import rag_generation_prompt
from ..utils import parse_with_repair
from . import FAILED, OK, ArmResult, Commission
from .naive import build_prompt as build_naive_prompt
from .vector_store import FlatBankIndex

_index: FlatBankIndex | None = None


def index_for(context) -> FlatBankIndex:
    """One index per bank, kept warm for the life of the process, like the pipeline's."""
    global _index
    if _index is None or _index.bank is not context.exemplars_bank:
        _index = FlatBankIndex(
            bank=context.exemplars_bank,
            primary_text=context.exemplars_profile.primary_text,
            type_key_of=context.exemplars_profile.type_key_of_safe,
        )
    return _index


def build_query(commission: Commission) -> str:
    """Everything this arm has to search with: the topic and the free instruction.

    No `EMBEDDING_QUERY_PREFIX` — that prefix talks about curriculum concepts and was
    measured as an optimisation of the system, so it belongs to the system.
    """
    parts = [", ".join(commission.concepts)]
    if commission.instructions.strip():
        parts.append(commission.instructions.strip())
    return "\n".join(parts)


def run(commission: Commission, context) -> ArmResult:
    item_type = context.exemplars_profile.item_type(commission.item_type)
    started = time.perf_counter()

    query = build_query(commission)
    retrieved = index_for(context).search(query, config.EVAL_RAG_TOP_K, item_type.key)
    exemplar_ids = [item_id for item_id, _ in retrieved]
    logger.info(
        f"RAG plano: {len(exemplar_ids)} ejemplar(es) por coseno — "
        + ", ".join(f"{item_id} ({score:.3f})" for item_id, score in retrieved)
    )

    exemplars = [context.exemplars_bank[item_id] for item_id in exemplar_ids]
    prompt = rag_generation_prompt(
        naive_prompt=build_naive_prompt(commission, context),
        exemplars_block=build_few_shot_block(item_type, exemplars),
        rules_block="\n".join(f"- {rule}" for rule in item_type.general_generation_rules),
        schema=item_type.schema_str(),
    )

    resp = inference.generate_stream(
        model=config.CONTENT_GENERATION_LLM,
        prompt=prompt,
        think=commission.think,
        on_token=progress.token_sink("eval"),
    )
    raw = resp.response or (resp.thinking or "")

    item, error = parse_with_repair(
        raw,
        lambda text: parse_item(
            inference.split_thinking(text).response, commission.fixed, item_type
        ),
        repair_model=config.REPAIR_LLM,
        max_attempts=config.MAX_JSON_REPAIR_TRIES,
        shape="objeto",
        format=item_type.stripped_schema(),
    )

    return ArmResult(
        arm="rag",
        status=OK if item is not None else FAILED,
        item=item.model_dump(mode="json") if item is not None else None,
        raw_response=raw,
        prompt=prompt,
        model=config.CONTENT_GENERATION_LLM,
        provider=inference.engine_name(),
        exemplar_ids=exemplar_ids,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        error=None if item is not None else str(error),
    )
