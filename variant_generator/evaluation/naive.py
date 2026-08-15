"""Arm 1 — a commercial model with the prompt an average user would type.

Besides being the lower anchor, this arm answers the question every defence of a local
system gets asked: «¿no sería más fácil usar un modelo comercial grande?». With data,
the answer stops being an opinion.

A dead provider does not stop a session: the arm records itself `unavailable` with its
reason and the comparison goes on with two proposals.
"""

import time

from loguru import logger

from .. import config
from ..content_generator import parse_item
from ..prompts import naive_generation_prompt
from ..utils import parse_with_repair
from . import FAILED, OK, UNAVAILABLE, ArmResult, ArmUnavailable, Commission
from . import external


def build_prompt(commission: Commission, context) -> str:
    item_type = context.content_profile.item_type(commission.item_type)
    return naive_generation_prompt(
        context=context.content_profile.content_context,
        concepts=commission.concepts,
        keys=list(item_type.field_specs),
        fixed=commission.fixed,
        instructions=commission.instructions,
    )


def run(commission: Commission, context) -> ArmResult:
    item_type = context.content_profile.item_type(commission.item_type)
    prompt = build_prompt(commission, context)
    started = time.perf_counter()

    def elapsed() -> int:
        return round((time.perf_counter() - started) * 1000)

    try:
        raw = external.generate(prompt)
    except ArmUnavailable as e:
        logger.warning(f"External arm unavailable: {e}")
        return ArmResult(
            arm="naive",
            status=UNAVAILABLE,
            item=None,
            raw_response="",
            prompt=prompt,
            model=config.EVAL_EXTERNAL_MODEL_ID,
            provider=config.EVAL_EXTERNAL_PROVIDER,
            exemplar_ids=[],
            elapsed_ms=elapsed(),
            error=str(e),
        )

    # Same parser and the same repair budget as the other two arms: this arm must not
    # lose over a crooked JSON that the system's would have had repaired.
    item, error = parse_with_repair(
        raw,
        lambda text: parse_item(text, commission.fixed, item_type),
        repair_model=config.REPAIR_LLM,
        max_attempts=config.MAX_JSON_REPAIR_TRIES,
        shape="objeto",
    )

    return ArmResult(
        arm="naive",
        status=OK if item is not None else FAILED,
        item=item.model_dump(mode="json") if item is not None else None,
        raw_response=raw,
        prompt=prompt,
        model=config.EVAL_EXTERNAL_MODEL_ID,
        provider=config.EVAL_EXTERNAL_PROVIDER,
        exemplar_ids=[],
        elapsed_ms=elapsed(),
        error=None if item is not None else str(error),
    )
