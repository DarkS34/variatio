"""Arm 1 — a commercial model with the prompt an average user would type.

Besides being the lower anchor, this arm answers the question every defence of a local
system gets asked: «¿no sería más fácil usar un modelo comercial grande?». With data,
the answer stops being an opinion.

A dead provider does not stop a session: the arm records itself `unavailable` with its
reason and the comparison goes on with two proposals.
"""

import time

from loguru import logger

from variatio import config
from variatio.core.repair import parse_with_repair
from variatio.variatio import parse_item

from .. import FAILED, OK, UNAVAILABLE, ArmResult, ArmUnavailable, Commission
from .. import prompts as study_prompts
from . import external


def build_prompt(commission: Commission, context) -> str:
    item_type = context.exemplars_profile.item_type(commission.item_type)
    # The three canonical facts, not the narrative. This arm composes a sentence a person
    # would type, and handing it synthesised prose would change what the baseline measures.
    return study_prompts.of(context.language).naive_generation_prompt(
        subject=context.content_context.subject,
        educational_level=context.content_context.educational_level,
        language_of_instruction=context.content_context.language_of_instruction,
        concepts=commission.concepts,
        keys=list(item_type.field_specs),
        fixed=commission.fixed,
        instructions=commission.instructions,
    )


def run(commission: Commission, context) -> ArmResult:
    item_type = context.exemplars_profile.item_type(commission.item_type)
    prompt = build_prompt(commission, context)
    started = time.perf_counter()

    def elapsed() -> int:
        return round((time.perf_counter() - started) * 1000)

    try:
        answer = external.generate(prompt, item_type.stripped_schema())
    except ArmUnavailable as e:
        logger.warning(f"Propuesta externa no disponible: {e}")
        # Nobody answered, so there is no answering provider to name: the record keeps the
        # head of the chain, which is who the arm would have asked.
        provider, model = external.primary()
        return ArmResult(
            arm="naive",
            status=UNAVAILABLE,
            item=None,
            raw_response="",
            prompt=prompt,
            model=model,
            provider=provider,
            exemplar_ids=[],
            elapsed_ms=elapsed(),
            error=str(e),
        )

    # Same parser and the same repair budget as the other two arms: this arm must not
    # lose over a crooked JSON that the system's would have had repaired.
    item, error = parse_with_repair(
        answer.text,
        lambda text: parse_item(text, commission.fixed, item_type),
        repair_model=config.REPAIR_LLM,
        max_attempts=config.MAX_JSON_REPAIR_TRIES,
        shape="objeto",
        format=item_type.stripped_schema(),
        # The workspace's set, not this arm's: what is repaired is JSON, not the baseline.
        # The two prompts that MAKE this arm a baseline are `study/prompts/`'s.
        prompts=context.prompts,
    )

    # From the ANSWER, not from config: the provider chain may have fallen back, and a
    # session filed under Gemini that Groq actually produced is a corrupted measurement.
    return ArmResult(
        arm="naive",
        status=OK if item is not None else FAILED,
        item=item.model_dump(mode="json") if item is not None else None,
        raw_response=answer.text,
        prompt=prompt,
        model=answer.model,
        provider=answer.provider,
        exemplar_ids=[],
        elapsed_ms=elapsed(),
        error=None if item is not None else str(error),
    )
