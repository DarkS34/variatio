"""The two ways the tutor asks a model for a JSON object, and how it reads the answer.

One helper for the criteria builder and the classifier, so the rule about grammars lives once:
a call that reasons cannot keep a grammar in this stack, and a remotely served model drops it
for the heavier reason `exemplars_bank_builder` measured — Cerebras' constrained decoding
writes every non-ASCII character as a broken `\\u00XX`, and both calls here write Spanish. A
call without its grammar is shown the schema in the prompt instead, and its answer goes
through the repair like any other.
"""

import json
import re

from loguru import logger

from variatio import config as pipeline_config
from variatio.core import inference
from variatio.core.repair import parse_with_repair

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def ask_object(
    prompt: str,
    schema: dict,
    *,
    model: str,
    think: bool | str,
    phase: str,
    tutor_prompts,
    prompts,
    max_output_tokens: int | None = None,
) -> dict | None:
    """Ask `model` for one JSON object and return it parsed, or None when even repair failed."""
    format = grammar_for(model, schema, think)
    text = prompt if format is not None else prompt + "\n\n" + tutor_prompts.schema_text(schema)
    response = inference.generate(
        model=model,
        prompt=text,
        think=think,
        format=format,
        sampling=inference.sampling(phase, think),
        max_output_tokens=max_output_tokens,
    )
    raw = response.response or (response.thinking or "")
    result, error = parse_with_repair(
        raw,
        parse_object,
        repair_model=pipeline_config.REPAIR_LLM,
        max_attempts=pipeline_config.MAX_JSON_REPAIR_TRIES,
        shape=tutor_prompts.SHAPE_OBJECT,
        format=format,
        prompts=prompts,
        log_prefix="[tutor] ",
    )
    if result is None:
        logger.warning(f"[tutor] '{model}' no devolvió un objeto legible: {error}")
    return result


def grammar_for(model: str, schema: dict, think: bool | str) -> dict | None:
    """Return the schema as the call's grammar, or None when a grammar would cost the call."""
    if think:
        return None
    try:
        remote = inference.remote_models()
    except inference.InferenceError:
        remote = frozenset()
    return None if model in remote else schema


def parse_object(text: str) -> tuple[dict | None, str | None]:
    """Parse the one JSON object an answer holds, stripping reasoning and code fences first."""
    body = _FENCE.sub("", inference.split_thinking(text).response or "").strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None, "no JSON object in the answer"
    try:
        value = json.loads(body[start : end + 1])
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "the answer is not a JSON object"
    return value, None
