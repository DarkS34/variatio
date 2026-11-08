"""Shape a grammar and a reasoning level into what Cerebras' strict mode accepts."""

import hashlib
import json

from loguru import logger

from ... import config

STRICT_SCHEMA_MAX_CHARS = 5000
_WRAPPER_NAME = "lista"

_UNSUPPORTED_KEYWORDS = ("pattern", "format", "minItems", "maxItems", "minLength", "maxLength")
# Pydantic titles every field it writes and the decoder never reads them: metadata, never
# shape, and pure weight against the 5 000-character cap — one real extraction schema
# measured 5 001 characters with them and 4 502 without.
_NOISE_KEYWORDS = ("title",)
_DROPPED_KEYWORDS = _UNSUPPORTED_KEYWORDS + _NOISE_KEYWORDS
_SUBSCHEMA_KEYS = ("items", "prefixItems", "anyOf", "allOf", "oneOf", "additionalProperties")
_SCHEMA_MAPS = ("properties", "$defs", "definitions")


def strict_schema(schema: dict) -> dict:
    """Adapt a JSON Schema to what Cerebras' strict mode accepts.

    Strict mode refuses the keywords Ollama's grammar merely ignores — `pattern`,
    `format`, the four `min`/`max` bounds — refuses `const` outright, and demands
    `additionalProperties: false` on every object that does not declare one of its own.
    `const` is the one refusal with a lossless translation and is rewritten as an `enum` of
    one; dropping the rest is lossy on purpose, since what a `pattern` guaranteed is what
    `parse_with_repair` and each component's parser re-check anyway.

    An object that DOES declare an `additionalProperties` schema is an open-ended map and
    is left alone: closing it rewrites the value's own type as `false`, leaving an object
    that can hold no field at all, and Cerebras answers 400. Such a map costs strict mode
    itself — measured, a typed one is refused just the same — not its shape.
    """
    return _walk(schema)


def _walk(node: object) -> object:
    """Rewrite one schema node and everything nested inside it."""
    if isinstance(node, list):
        return [_walk(part) for part in node]
    if not isinstance(node, dict):
        return node
    out: dict = {}
    for key, value in node.items():
        if key in _DROPPED_KEYWORDS:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _walk(sub) for name, sub in value.items()}
        elif key in _SUBSCHEMA_KEYS:
            out[key] = _walk(value)
        elif key == "const":
            out["enum"] = [value]
        else:
            out[key] = value
    if "additionalProperties" in node:
        return out
    if out.get("type") == "object" or "properties" in out:
        out["additionalProperties"] = False
    return out


def _open_map(node: object) -> bool:
    """Whether any object in the schema takes keys the schema does not name.

    Strict mode refuses those, so a schema containing one is asked for without it.
    """
    if isinstance(node, list):
        return any(_open_map(part) for part in node)
    if not isinstance(node, dict):
        return False
    if node.get("type") == "object" and "properties" not in node and "anyOf" not in node:
        return True
    for key, value in node.items():
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            if any(_open_map(sub) for sub in value.values()):
                return True
        elif key in _SUBSCHEMA_KEYS and _open_map(value):
            return True
    return False


# A degradation is a property of the SCHEMA and not of the call, and the same schema goes
# out on every call of a phase and again on every repair: one bank build printed the size
# warning 29 times. A build has a process of its own, so once per process misses nothing.
_WARNED: set[str] = set()



def _unwrap(text: str) -> str:
    """Return the array inside a one-key wrapper object, or `text` unchanged."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, dict) and set(data) == {"items"}:
        return json.dumps(data["items"], ensure_ascii=False)
    return text


def reasoning_effort(think: bool | str | None) -> str | None:
    """Translate `think` into Cerebras' `reasoning_effort`, at the last hop before the call.

    The same translation `OllamaEngine._think_option` does, in the other dialect: the
    levels are "none"/"low"/"medium"/"high", Cerebras has no "max", so Ollama's top level
    maps down to "high". A string is a per-phase effort already resolved by
    `settings.derived` and travels untouched; `True` becomes `config.DEFAULT_THINK_EFFORT`.

    It assumes every routed model has an off switch. Some families answer 400 "Unsupported
    reasoning effort: none" and would need `False` floored at their own minimum; none is
    routed here today.
    """
    if think is None:
        return None
    if think is False:
        return "none"
    effort = think if isinstance(think, str) else config.DEFAULT_THINK_EFFORT
    return "high" if effort == "max" else effort


def response_format(format: dict | str | None) -> dict | None:
    """Build Cerebras' `response_format`, degrading where strict mode cannot hold.

    Strict mode demands an OBJECT at the root — an array root answers 400 "Extra top level
    keys found in JSON schema: {'items'}" — so an array schema is wrapped in a one-key
    object and `generate` unwraps the reply before any parser sees it. The wrapper's `name`
    is the marker, which is why `_WRAPPER_NAME` must never be the plain "respuesta".
    Wrapped implies strict: the wrap is only taken when the wrapper clears every other
    check, so a reply to a wrapped schema is decoder-guaranteed to be the object `_unwrap`
    expects.

    `strict` is dropped in three cases — a non-object root that cannot be wrapped, an
    open-keyed map, and a schema above `STRICT_SCHEMA_MAX_CHARS`. The shape still travels
    and still guides: measured, the same call answered arrays with the map typed and bare
    strings with it untyped. What is lost is the decoder's guarantee, which
    `parse_with_repair` takes over from there.
    """
    if format is None:
        return None
    if isinstance(format, str):
        return {"type": "json_object"}
    adapted = strict_schema(format)
    name = "respuesta"
    if adapted.get("type") != "object" and not _open_map(adapted):
        candidate = {
            "type": "object",
            "properties": {"items": adapted},
            "required": ["items"],
            "additionalProperties": False,
        }
        packed = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
        if len(packed) <= STRICT_SCHEMA_MAX_CHARS:
            adapted = candidate
            name = _WRAPPER_NAME
    compact = json.dumps(adapted, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.md5(compact.encode("utf-8")).hexdigest()
    strict = True
    if adapted.get("type") != "object":
        _warn_once(
            f"root:{digest}",
            "[cerebras] The schema root is not an object, which strict mode demands; "
            "asking without 'strict'",
        )
        strict = False
    if _open_map(adapted):
        _warn_once(
            f"map:{digest}",
            "[cerebras] The schema declares an open-keyed object, which strict mode "
            "refuses; asking without 'strict'",
        )
        strict = False
    if len(compact) > STRICT_SCHEMA_MAX_CHARS:
        _warn_once(
            f"size:{digest}",
            f"[cerebras] The schema measures {len(compact)} characters (strict mode's "
            f"limit: {STRICT_SCHEMA_MAX_CHARS}); asking without 'strict'",
        )
        strict = False
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": strict, "schema": adapted},
    }


def _warn_once(digest: str, message: str) -> None:
    """Log `message` the first time this process sees `digest`."""
    if digest in _WARNED:
        return
    _WARNED.add(digest)
    logger.warning(message)
