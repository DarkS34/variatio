"""Reading the model's answer back: JSON repair and the relation vocabulary.

`valid_relations` is the authority on the vocabulary and on the order of a triple, and it
stays so on purpose: the `format` schemas pin a triple to three strings and no further,
because Ollama's converter accepts a per-slot `enum` and then ignores it.
"""

from json_repair import repair_json
from loguru import logger

from ... import config
from ...core.repair import parse_with_repair


def parse_object(
    response: str, log_prefix: str, format: dict, max_attempts: int, prompts
) -> dict | None:
    """Read one answer as an object, escalating to the repair model, `None` if unrecoverable."""
    result, error = parse_with_repair(
        response,
        parse_json_object,
        repair_model=config.REPAIR_LLM,
        max_attempts=max_attempts,
        shape="object",
        format=format,
        log_prefix=log_prefix,
        prompts=prompts,
    )
    if result is None:
        logger.warning(f"{log_prefix}Unrecoverable JSON: {error}")
    return result


def parse_json_object(text: str) -> tuple[dict | None, str | None]:
    """Repair the text into a JSON object, or say why it is not one."""
    raw = repair_json(text, return_objects=True)
    if not isinstance(raw, dict):
        return None, "model did not return a JSON object"
    return raw, None


def valid_relations(raw: list, schema, allowed: set[str] | None) -> list[list[str]]:
    """Keep the triples whose relation is in the vocabulary and whose endpoints are allowed."""
    out = []
    for entry in raw or []:
        triple = _triple(entry)
        if triple is None or triple[1] not in schema:
            continue
        if allowed is not None and (triple[0] not in allowed or triple[2] not in allowed):
            continue
        out.append(triple)
    return out


def _triple(entry) -> list[str] | None:
    """One well-formed `[source, relation, target]` of stripped strings, or `None`."""
    if not (isinstance(entry, list) and len(entry) == 3):
        return None
    if not all(isinstance(x, str) for x in entry):
        return None
    source, relation, target = (x.strip() for x in entry)
    if not (source and target) or source == target:
        return None
    return [source, relation, target]


def concepts_with_definitions(raw: list) -> tuple[list[str], dict[str, str]]:
    """Read the concept list as `(names, definitions)`, deduplicated in order of arrival.

    A concept arrives as `{"name", "definition"}`, but a bare string is still read: the
    grammar pins the shape for the two passes that run under it, and nothing else should
    fail on an answer the older prompt would have produced.
    """
    names: list[str] = []
    definitions: dict[str, str] = {}
    for entry in raw or []:
        if isinstance(entry, str):
            name, definition = entry, ""
        elif isinstance(entry, dict):
            name, definition = entry.get("name"), entry.get("definition")
        else:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name not in names:
            names.append(name)
        if isinstance(definition, str) and definition.strip() and name not in definitions:
            definitions[name] = clip_definition(definition)
    return names, definitions


def clip_definition(text: str) -> str:
    """Collapse the whitespace of a definition and cut it on a word at the cap."""
    text = " ".join(text.split())
    limit = config.KG_DEFINITION_MAX_CHARS
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip(" ,;:") + "…"
