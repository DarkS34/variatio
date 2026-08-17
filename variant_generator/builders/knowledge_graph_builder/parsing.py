"""Reading the model's answer back: JSON repair and the relation vocabulary.

`valid_relations` is the authority on the vocabulary and on the order of a triple, and it
stays so on purpose: the `format` schemas pin a triple to three strings and no further,
because Ollama's converter accepts a per-slot `enum` and then ignores it.
"""

from json_repair import repair_json
from loguru import logger

from ... import config
from ...utils import parse_with_repair


def parse_json_object(text: str) -> tuple[dict | None, str | None]:
    raw = repair_json(text, return_objects=True)
    if not isinstance(raw, dict):
        return None, "model did not return a JSON object"
    return raw, None


def parse_object(
    response: str, log_prefix: str, format: dict, max_attempts: int
) -> dict | None:
    result, error = parse_with_repair(
        response,
        parse_json_object,
        repair_model=config.REPAIR_LLM,
        max_attempts=max_attempts,
        shape="object",
        format=format,
        log_prefix=log_prefix,
    )
    if result is None:
        logger.warning(f"{log_prefix}JSON irrecuperable: {error}")
    return result


def valid_relations(raw: list, schema, allowed: set[str] | None) -> list[list[str]]:
    out = []
    for triple in raw or []:
        if not (isinstance(triple, list) and len(triple) == 3):
            continue
        if not all(isinstance(x, str) for x in triple):
            continue
        source, relation, target = (x.strip() for x in triple)
        if not (source and target) or source == target or relation not in schema:
            continue
        if allowed is not None and (source not in allowed or target not in allowed):
            continue
        out.append([source, relation, target])
    return out
