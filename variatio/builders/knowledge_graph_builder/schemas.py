"""One schema per shape the KG prompts already draw in their `# OUTPUT` block.

Only the two passes that do NOT think are constrained at the call itself; the rest reach
these through their repair, which is where an unusable answer was costing three calls that
could not fix a schema error.
"""

# A triple is pinned to three strings and NO further. Naming the middle element with an
# `enum` needs `prefixItems`, which Ollama's converter accepts and then ignores — asked for
# `[string, <relation key>, string]` it answered with the type in slot 2. A schema this
# engine accepts is not necessarily one it enforces, so `valid_relations` stays the
# authority on the vocabulary and on the order.
_RELATIONS_SCHEMA = {
    "type": "array",
    "items": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
}

# A concept carries its one-line definition from the chunk that introduced it, so every
# later pass — merging, dropping, placing, linking — judges an idea and not a bare name.
_CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "definition": {"type": "string"}},
    "required": ["name", "definition"],
}

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "concepts": {"type": "array", "items": _CONCEPT_SCHEMA},
        "relations": _RELATIONS_SCHEMA,
    },
    "required": ["concepts", "relations"],
}

LINK_SCHEMA = {
    "type": "object",
    "properties": {"relations": _RELATIONS_SCHEMA},
    "required": ["relations"],
}


MERGE_SCHEMA = {
    "type": "object",
    "properties": {
        "merges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "canonical": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["canonical", "aliases"],
            },
        }
    },
    "required": ["merges"],
}

# `drop`, `domains` and `non_taggable` are open-ended maps — the keys are concept or domain
# names the model writes — so what the schema pins is the ENVELOPE: the top-level key and
# the value type. The `drop` parser also accepts a bare list, for the unconstrained path.
DROP_SCHEMA = {
    "type": "object",
    "properties": {"drop": {"type": "object", "additionalProperties": {"type": "string"}}},
    "required": ["drop"],
}

# Two shapes for one word: the naming pass answers with the domain NAMES alone and the
# assignment pass with the map of who goes where. The decoder enforces whichever it is
# handed, so asking for names under `DOMAINS_SCHEMA` would license the enumeration again.
DOMAIN_NAMES_SCHEMA = {
    "type": "object",
    "properties": {"domains": {"type": "array", "items": {"type": "string"}}},
    "required": ["domains"],
}

DOMAINS_SCHEMA = {
    "type": "object",
    "properties": {
        "domains": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        }
    },
    "required": ["domains"],
}

UNITS_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "opens_at": {"type": "integer"},
                },
                "required": ["name", "opens_at"],
            },
        }
    },
    "required": ["units"],
}

TAGGABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "non_taggable": {"type": "object", "additionalProperties": {"type": "string"}}
    },
    "required": ["non_taggable"],
}
