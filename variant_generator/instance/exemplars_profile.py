import copy
import json
import operator
import re
from functools import reduce
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, create_model

ITEM_TYPE_KEY = "item_type"

RESERVED_FIELD_NAMES = (ITEM_TYPE_KEY, "id", "source", "concepts", "primary_concept")

DRIFT_ASPECTS = ("type", "enum", "decided_by")


def _fields_by_type(raw: dict) -> dict[str, dict]:
    item_types = raw.get("item_types") if isinstance(raw, dict) else None
    if not isinstance(item_types, dict):
        return {}
    return {
        key: dict(spec.get("fields") or {})
        for key, spec in item_types.items()
        if isinstance(spec, dict)
    }


def _field_aspects(spec: dict) -> dict:
    schema = spec.get("schema") if isinstance(spec, dict) else None
    schema = schema if isinstance(schema, dict) else {}
    decided_by = spec.get("decided_by") if isinstance(spec, dict) else None
    return {
        "type": schema.get("type"),
        "enum": list(schema["enum"]) if isinstance(schema.get("enum"), list) else None,
        "decided_by": decided_by or "model",
    }


def profile_drift(curated: dict, draft: dict) -> dict:
    before = _fields_by_type(curated)
    after = _fields_by_type(draft)
    added: dict[str, list[str]] = {}
    removed: dict[str, dict] = {}
    changed: dict[str, dict] = {}

    for type_key in sorted(set(before) | set(after)):
        old_fields = before.get(type_key, {})
        new_fields = after.get(type_key, {})
        for name in new_fields:
            if name not in old_fields:
                added.setdefault(name, []).append(type_key)
        for name, spec in old_fields.items():
            aspects = _field_aspects(spec)
            if name not in new_fields:
                entry = removed.setdefault(name, {"item_types": [], "decided_by": aspects["decided_by"]})
                entry["item_types"].append(type_key)
                continue
            fresh = _field_aspects(new_fields[name])
            diffs = [aspect for aspect in DRIFT_ASPECTS if aspects[aspect] != fresh[aspect]]
            if diffs:
                entry = changed.setdefault(name, {"item_types": [], "aspects": []})
                entry["item_types"].append(type_key)
                entry["aspects"] = sorted(set(entry["aspects"]) | set(diffs), key=DRIFT_ASPECTS.index)

    return {
        "added": [{"field": name, "item_types": types} for name, types in added.items()],
        "removed": [{"field": name, **entry} for name, entry in removed.items()],
        "changed": [{"field": name, **entry} for name, entry in changed.items()],
    }


class ItemType:
    def __init__(self, key: str, raw: dict):
        self.key = key
        self.label: str = raw.get("label") or key
        self.description: str = raw.get("description") or ""
        self.primary_field: str = raw["primary_field"]
        self.embed_fields: list[str] = list(raw.get("embed_fields") or [self.primary_field])
        self.general_generation_rules: list[str] = list(raw.get("general_generation_rules") or [])
        self.field_specs: dict[str, dict] = raw["fields"]
        self.content_item: type[BaseModel] = self._build_content_item()

    def _build_content_item(self) -> type[BaseModel]:
        fields = {
            name: ExemplarsProfile._spec_to_field(spec) for name, spec in self.field_specs.items()
        }
        model = create_model(f"ContentItem_{self.key}", **fields)
        model.PRIMARY_FIELD = self.primary_field
        model.ITEM_TYPE = self.key
        return model

    def stripped_schema(self) -> dict:
        schema = copy.deepcopy(self.content_item.model_json_schema())
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("guidance", None)
        return schema

    def schema_str(self) -> str:
        return json.dumps(self.stripped_schema(), indent=2, ensure_ascii=False)

    def field_guidance(self, task: str) -> dict[str, str]:
        if task not in ExemplarsProfile._GUIDANCE_KEYS:
            raise ValueError(
                f"Unknown task '{task}'; expected one of {list(ExemplarsProfile._GUIDANCE_KEYS)}"
            )
        out: dict[str, str] = {}
        for name, spec in self.field_specs.items():
            text = (spec.get("guidance") or {}).get(task)
            if text:
                out[name] = text
        return out

    def primary_text(self, item: dict) -> str:
        if self.primary_field not in item:
            raise ValueError(
                f"Item is missing its primary field '{self.primary_field}' "
                f"(item type '{self.key}')"
            )
        return str(item[self.primary_field] or "")

    def embed_text(self, item: dict, field_max_chars: int = 0) -> str:
        primary = self.primary_text(item)
        if self.embed_fields == [self.primary_field]:
            return primary

        parts: list[str] = []
        for name in self.embed_fields:
            if name == self.primary_field:
                parts.append(primary)
                continue
            rendered = self._render_value(item.get(name))
            if rendered:
                if field_max_chars and len(rendered) > field_max_chars:
                    rendered = rendered[:field_max_chars].rstrip() + " […]"
                parts.append(f"{name}:\n{rendered}")
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _render_value(value) -> str:
        if value is None or isinstance(value, bool):
            return "" if value is None else str(value)
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            lines = [ItemType._render_value(v) for v in value]
            return "\n".join(f"- {line}" for line in lines if line)
        if isinstance(value, dict):
            return "\n".join(
                f"- {k}: {ItemType._render_value(v)}" for k, v in value.items() if v is not None
            )
        return str(value)


class ExemplarsProfile:
    _REQUIRED_KEYS: ClassVar[tuple] = ("item_types",)
    _TYPE_REQUIRED_KEYS: ClassVar[tuple] = ("primary_field", "fields")
    _SCALAR_TYPES: ClassVar[dict] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "null": type(None),
    }
    _GUIDANCE_KEYS: ClassVar[tuple] = ("extraction", "generation")
    _DECIDED_BY_VALUES: ClassVar[tuple] = ("user", "model")
    _UNDECIDABLE_TYPES: ClassVar[tuple] = ("array", "object")
    NAME_RE: ClassVar[re.Pattern] = re.compile(r"^[a-z][a-z0-9_]*$")

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._raw = self._load(self.path)
        self._validate(self._raw)
        self.item_types: dict[str, ItemType] = {
            key: ItemType(key, spec)
            for key, spec in self._raw["item_types"].items()
        }

    # What subject this is left the profile on 2026-08-22 and became `content_context.json`,
    # because the KG build has to be able to write it and a build writes exactly one artifact.
    # A profile written before that still carries the key; this exposes it so `initialize`
    # can fall back to it and say so, rather than silently losing the subject. Nothing on
    # the graph's path reads it -- that dependency is what the move removed.
    @property
    def legacy_content_context(self) -> dict:
        raw = self._raw.get("content_context")
        return dict(raw) if isinstance(raw, dict) else {}

    @property
    def type_keys(self) -> list[str]:
        return list(self.item_types)

    @property
    def default_type(self) -> str:
        return next(iter(self.item_types))

    def item_type(self, key: str | None = None) -> ItemType:
        if key is None:
            return self.item_types[self.default_type]
        if key not in self.item_types:
            raise ValueError(
                f"Unknown item type '{key}'; the profile declares {self.type_keys}"
            )
        return self.item_types[key]

    def type_key_of(self, item: dict) -> str:
        key = item.get(ITEM_TYPE_KEY)
        if key is None:
            if len(self.item_types) == 1:
                return self.default_type
            raise ValueError(
                f"Item has no '{ITEM_TYPE_KEY}' and the profile declares {self.type_keys}"
            )
        if key not in self.item_types:
            raise ValueError(
                f"Item declares unknown {ITEM_TYPE_KEY} '{key}'; "
                f"the profile declares {self.type_keys}"
            )
        return str(key)

    def type_key_of_safe(self, item: dict) -> str | None:
        try:
            return self.type_key_of(item)
        except ValueError:
            return None

    def item_type_of(self, item: dict) -> ItemType:
        return self.item_types[self.type_key_of(item)]

    def primary_text(self, item: dict) -> str:
        return self.item_type_of(item).primary_text(item)

    def embed_text(self, item: dict, field_max_chars: int = 0) -> str:
        return self.item_type_of(item).embed_text(item, field_max_chars)

    def primary_fields(self) -> dict[str, str]:
        return {key: item_type.primary_field for key, item_type in self.item_types.items()}

    def embed_fields(self) -> dict[str, list[str]]:
        return {key: list(item_type.embed_fields) for key, item_type in self.item_types.items()}

    # Feeds the embedding caches' fingerprint: changing which fields are indexed changes
    # every vector, and the `.npz` files are keyed by model + prefixes only. Without this
    # a profile edit would silently reuse vectors built from a different text.
    #
    # Empty when every modality indexes its primary field alone, which is the rule that
    # was in force before `embed_fields` existed and produces byte-identical text. A
    # profile that declares nothing new must not invalidate caches it still matches.
    @property
    def embed_signature(self) -> str:
        fields = self.embed_fields()
        if all(names == [self.item_types[key].primary_field] for key, names in fields.items()):
            return ""
        return json.dumps(fields, sort_keys=True, ensure_ascii=False)

    # Everything that iterates the bank (embedding, tagging, few-shot) resolves each item
    # against its declared type, so one item the profile cannot place would blow up deep
    # inside a loop. Checking the whole bank at once buys a single actionable error instead.
    def unplaceable_items(self, bank: dict) -> dict[str, str]:
        problems: dict[str, str] = {}
        for item_id, item in bank.items():
            try:
                self.primary_text(item)
            except ValueError as exc:
                problems[item_id] = str(exc)
        return problems

    # Reported, never truncated here. Ollama's two embedding endpoints disagree about
    # oversized input — the batch one silently truncates, the single-text one returns a
    # 500 — so an item over budget indexes fine and then fails at tagging with an opaque
    # error. Naming it up front is the difference between a diagnosable warning and that.
    def oversized_embed_items(
        self, bank: dict, max_chars: int, field_max_chars: int = 0
    ) -> dict[str, int]:
        sizes: dict[str, int] = {}
        for item_id, item in bank.items():
            size = len(self.embed_text(item, field_max_chars))
            if size > max_chars:
                sizes[item_id] = size
        return sizes

    @staticmethod
    def _load(path: Path) -> dict:
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    # Editors (the CLI's own builder, the web UI) need to know whether a candidate
    # profile would load *before* writing it. Same rules, same errors, one authority.
    @classmethod
    def validate_raw(cls, raw: dict) -> None:
        cls._validate(raw)
        for key, spec in raw["item_types"].items():
            fields = {
                name: cls._spec_to_field(field_spec)
                for name, field_spec in spec["fields"].items()
            }
            create_model(f"ItemCandidate_{key}", **fields)

    @property
    def raw(self) -> dict:
        return copy.deepcopy(self._raw)

    @classmethod
    def _validate(cls, raw: dict) -> None:
        if not isinstance(raw, dict):
            raise TypeError("ExemplarsProfile root must be an object")

        missing = [k for k in cls._REQUIRED_KEYS if k not in raw]
        if missing:
            raise ValueError(f"ExemplarsProfile missing required keys: {missing}")

        if not isinstance(raw["item_types"], dict) or not raw["item_types"]:
            raise ValueError("'item_types' must be a non-empty object")

        for key, spec in raw["item_types"].items():
            cls._validate_item_type(key, spec)

    @classmethod
    def _validate_item_type(cls, key: str, spec: dict) -> None:
        if not cls.NAME_RE.match(key):
            raise ValueError(
                f"Item type '{key}' must match {cls.NAME_RE.pattern} "
                f"(lowercase ASCII, snake_case, no accents)"
            )
        if not isinstance(spec, dict):
            raise TypeError(f"Item type '{key}' must be an object")

        missing = [k for k in cls._TYPE_REQUIRED_KEYS if k not in spec]
        if missing:
            raise ValueError(f"Item type '{key}' missing required keys: {missing}")

        if not isinstance(spec["fields"], dict) or not spec["fields"]:
            raise ValueError(f"Item type '{key}': 'fields' must be a non-empty object")
        if not isinstance(spec["primary_field"], str):
            raise TypeError(f"Item type '{key}': 'primary_field' must be a string")
        if spec["primary_field"] not in spec["fields"]:
            raise ValueError(
                f"Item type '{key}': 'primary_field' = '{spec['primary_field']}' "
                f"is not declared in its 'fields'"
            )
        cls._validate_embed_fields(key, spec)
        rules = spec.get("general_generation_rules")
        if rules is not None and not isinstance(rules, list):
            raise ValueError(f"Item type '{key}': 'general_generation_rules' must be a list")
        for label_key in ("label", "description"):
            if label_key in spec and not isinstance(spec[label_key], str):
                raise ValueError(f"Item type '{key}': '{label_key}' must be a string")

        for name, field_spec in spec["fields"].items():
            cls._validate_field_name(key, name)
            cls._validate_field_spec(
                name, field_spec, is_primary=name == spec["primary_field"]
            )

    # The primary field is required in the list, not merely allowed: it is the only field
    # guaranteed to carry the item itself, and a profile that indexed `opciones` alone
    # would retrieve on the distractors. Order is preserved as declared.
    @classmethod
    def _validate_embed_fields(cls, key: str, spec: dict) -> None:
        embed_fields = spec.get("embed_fields")
        if embed_fields is None:
            return
        if not isinstance(embed_fields, list) or not embed_fields:
            raise ValueError(f"Item type '{key}': 'embed_fields' must be a non-empty list")
        unknown = [n for n in embed_fields if n not in spec["fields"]]
        if unknown:
            raise ValueError(
                f"Item type '{key}': 'embed_fields' names field(s) it does not declare: {unknown}"
            )
        if len(set(embed_fields)) != len(embed_fields):
            raise ValueError(f"Item type '{key}': 'embed_fields' has duplicates")
        if spec["primary_field"] not in embed_fields:
            raise ValueError(
                f"Item type '{key}': 'embed_fields' must include the primary field "
                f"'{spec['primary_field']}'"
            )

    @classmethod
    def _validate_field_name(cls, type_key: str, name: str) -> None:
        if not cls.NAME_RE.match(name):
            raise ValueError(
                f"Item type '{type_key}': field '{name}' must match {cls.NAME_RE.pattern} "
                f"(lowercase ASCII, snake_case, no accents, no ñ)"
            )
        if name in RESERVED_FIELD_NAMES:
            raise ValueError(
                f"Item type '{type_key}': '{name}' is reserved by the pipeline "
                f"(reserved: {list(RESERVED_FIELD_NAMES)})"
            )

    @classmethod
    def _validate_field_spec(cls, name: str, spec: dict, is_primary: bool = False) -> None:
        if not isinstance(spec, dict):
            raise TypeError(f"Field '{name}' spec must be an object")

        schema = spec.get("schema")
        if not isinstance(schema, dict) or not schema:
            raise ValueError(f"Field '{name}' must declare a non-empty 'schema' object")
        if "type" not in schema and "enum" not in schema:
            raise ValueError(f"Field '{name}' schema must declare 'type' or 'enum'")
        cls._validate_decided_by(name, spec, schema, is_primary)
        guidance = spec.get("guidance")
        if guidance is not None:
            if not isinstance(guidance, dict):
                raise ValueError(f"Field '{name}' 'guidance' must be an object")
            unknown = set(guidance) - set(cls._GUIDANCE_KEYS)
            if unknown:
                raise ValueError(
                    f"Field '{name}' 'guidance' has unknown keys: {sorted(unknown)} (allowed: {list(cls._GUIDANCE_KEYS)})"
                )

    @classmethod
    def _validate_decided_by(cls, name: str, spec: dict, schema: dict, is_primary: bool) -> None:
        decided_by = spec.get("decided_by")
        if decided_by is None:
            return
        if decided_by not in cls._DECIDED_BY_VALUES:
            raise ValueError(
                f"Field '{name}' 'decided_by' must be one of {list(cls._DECIDED_BY_VALUES)}, got {decided_by!r}"
            )
        if decided_by != "user":
            return
        if is_primary:
            raise ValueError(
                f"Field '{name}' is the primary field: it carries the item itself, so it cannot be 'decided_by': 'user'"
            )
        if "enum" not in schema and schema.get("type") in cls._UNDECIDABLE_TYPES:
            raise ValueError(
                f"Field '{name}' is of type '{schema['type']}': there is no choice to offer, so it cannot be 'decided_by': 'user'"
            )

    @classmethod
    def _spec_to_field(cls, spec: dict) -> tuple:
        schema = spec["schema"]
        py_type = cls._py_type(schema)
        kwargs: dict = {}
        if "description" in spec:
            kwargs["description"] = spec["description"]
        if "minLength" in schema:
            kwargs["min_length"] = schema["minLength"]
        if "maxLength" in schema:
            kwargs["max_length"] = schema["maxLength"]
        if "minimum" in schema:
            kwargs["ge"] = schema["minimum"]
        if "maximum" in schema:
            kwargs["le"] = schema["maximum"]
        guidance = spec.get("guidance")
        if guidance:
            kwargs["json_schema_extra"] = {"guidance": dict(guidance)}
        if "default" in schema:
            return (py_type, Field(default=schema["default"], **kwargs))
        return (py_type, Field(..., **kwargs))

    @classmethod
    def _py_type(cls, schema: dict):
        if "enum" in schema:
            values = schema["enum"]
            if not isinstance(values, list) or not values:
                raise ValueError("'enum' must be a non-empty list")
            return Literal[tuple(values)]
        t = schema["type"]
        if isinstance(t, list):
            if not t:
                raise ValueError("'type' list must be non-empty")
            # Recurse instead of assuming every member is scalar: `{"type": ["array",
            # "null"], "items": …}` is a list of options that may be absent, which is
            # ordinary once one profile declares several modalities. Rejecting it only
            # bought a repair round that ended up dropping the nullability.
            return reduce(
                operator.or_, (cls._py_type({**schema, "type": s}) for s in t)
            )
        if t == "array":
            items_schema = schema.get("items", {"type": "string"})
            return list[cls._py_type(items_schema)]
        if t == "object":
            return dict
        return cls._scalar(t)

    @classmethod
    def _scalar(cls, t: str | None):
        if t is None:
            t = "null"
        if t not in cls._SCALAR_TYPES:
            raise ValueError(f"Unsupported scalar type: '{t}'")
        return cls._SCALAR_TYPES[t]
