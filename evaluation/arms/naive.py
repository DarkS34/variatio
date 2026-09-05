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
from variatio.runtime.generator import parse_item

from .. import FAILED, OK, UNAVAILABLE, ArmResult, ArmUnavailable, Commission
from .. import prompts as evaluation_prompts
from . import external


def _spoken_fixed(commission: Commission, item_type) -> dict[str, object]:
    """Re-key the pinned fields by their human label, falling back to the field name.

    `nivel_dificultad` is an identifier of this system, not a word anybody says out loud,
    and this arm is the sentence somebody types in a hurry. The commission itself is left
    alone — only what the prompt SAYS is relabelled, never what `parse_item` validates.
    """
    spoken: dict[str, object] = {}
    for name, value in (commission.fixed or {}).items():
        spoken[item_type.field_specs.get(name, {}).get("label") or name] = value
    return spoken


def build_prompt(commission: Commission, context) -> str:
    """Render the baseline prompt: the three canonical facts plus the subject's context.

    The context block is `content_context.prompt_block()`, the same prose every prompt of
    the pipeline interpolates. It reaches this arm since 2026-09-04 because without it the
    two baselines invented the material — a programming course's exercises came back in
    whatever language the model favoured — and what was being measured was then the absence
    of a paragraph, not the absence of the system. The rag arm builds on this same prompt.
    """
    item_type = context.exemplars_profile.item_type(commission.item_type)
    return evaluation_prompts.of(context.language).naive_generation_prompt(
        subject=context.content_context.subject,
        educational_level=context.content_context.educational_level,
        language_of_instruction=context.content_context.language_of_instruction,
        context_block=context.content_context.prompt_block(),
        concepts=commission.concepts,
        keys=list(item_type.field_specs),
        fixed=_spoken_fixed(commission, item_type),
        instructions=commission.instructions,
    )


def run(commission: Commission, context) -> ArmResult:
    """Ask the commercial provider for one item and record who actually answered."""
    item_type = context.exemplars_profile.item_type(commission.item_type)
    prompt = build_prompt(commission, context)
    started = time.perf_counter()

    def elapsed() -> int:
        """Return the milliseconds spent so far, the failed attempts included."""
        return round((time.perf_counter() - started) * 1000)

    try:
        answer = external.generate(prompt)
    except ArmUnavailable as e:
        logger.warning(f"Propuesta externa no disponible: {e}")
        # Nobody answered, so the record keeps the head of the chain: who it would have asked.
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

    # Same parser and the same repair budget as the other two arms: this arm must not lose
    # over a crooked JSON that the system's would have had repaired.
    item, error = parse_with_repair(
        answer.text,
        lambda text: parse_item(text, commission.fixed, item_type),
        repair_model=config.REPAIR_LLM,
        max_attempts=config.MAX_JSON_REPAIR_TRIES,
        shape="objeto",
        format=item_type.stripped_schema(),
        # The workspace's set, not this arm's: what is repaired is JSON, not the baseline.
        prompts=context.prompts,
    )

    # Provider and model come from the ANSWER, not from config: the chain may have fallen
    # back, and a session filed under Gemini that Groq produced is a corrupted measurement.
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
