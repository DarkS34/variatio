import copy
import json
import operator
from functools import reduce
from pathlib import Path
from typing import Literal, ClassVar

from pydantic import BaseModel, Field, create_model

class ContentProfile:
    _REQUIRED_KEYS: ClassVar[tuple] = (
        "content_context",
        "general_generation_rules",
        "primary_field",
        "fields",
    )
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

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._raw = self._load(self.path)
        self._validate(self._raw)
        self.content_context: dict = self._raw["content_context"]
        self.general_generation_rules: list[str] = list(self._raw["general_generation_rules"])
        self.primary_field: str = self._raw["primary_field"]
        self.field_specs: dict[str, dict] = self._raw["fields"]
        self.content_item: type[BaseModel] = self._build_content_item()
        
    def _build_content_item(self) -> type[BaseModel]:
        fields = {
            name: self._spec_to_field(spec) for name, spec in self.field_specs.items()
        }
        model = create_model("ContentItem", **fields)
        model.PRIMARY_FIELD = self.primary_field
        return model

    @staticmethod
    def _load(path: Path) -> dict:
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    # Editors (the CLI's own builder, the web UI) need to know whether a candidate
    # profile would load *before* writing it. Same rules, same errors, one authority.
    @classmethod
    def validate_raw(cls, raw: dict) -> None:
        cls._validate(raw)
        fields = {name: cls._spec_to_field(spec) for name, spec in raw["fields"].items()}
        create_model("ContentItemCandidate", **fields)

    @property
    def raw(self) -> dict:
        return copy.deepcopy(self._raw)

    @classmethod
    def _validate(cls, raw: dict) -> None:
        if not isinstance(raw, dict):
            raise ValueError("ContentProfile root must be an object")
        
        missing = [k for k in cls._REQUIRED_KEYS if k not in raw]
        
        if missing:
            raise ValueError(f"ContentProfile missing required keys: {missing}")
        
        if not isinstance(raw["content_context"], dict) or not raw["content_context"]:
            raise ValueError("'content_context' must be a non-empty object")
        if not isinstance(raw["general_generation_rules"], list):
            raise ValueError("'general_generation_rules' must be a list")
        if not isinstance(raw["fields"], dict) or not raw["fields"]:
            raise ValueError("'fields' must be a non-empty object")
        if not isinstance(raw["primary_field"], str):
            raise ValueError("'primary_field' must be a string")
        if raw["primary_field"] not in raw["fields"]:
            raise ValueError(
                f"'primary_field' = '{raw['primary_field']}' is not declared in 'fields'"
            )
        for name, spec in raw["fields"].items():
            cls._validate_field_spec(name, spec, is_primary=name == raw["primary_field"])

    @classmethod
    def _validate_field_spec(cls, name: str, spec: dict, is_primary: bool = False) -> None:
        if not isinstance(spec, dict):
            raise ValueError(f"Field '{name}' spec must be an object")

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

    @property
    def user_decided_fields(self) -> list[str]:
        return [
            name
            for name, spec in self.field_specs.items()
            if spec.get("decided_by") == "user"
        ]

    def stripped_schema(self) -> dict:
        schema = copy.deepcopy(self.content_item.model_json_schema())
        for prop in schema.get("properties", {}).values():
            prop.pop("guidance", None)
        return schema

    def field_guidance(self, task: str) -> dict[str, str]:
        if task not in self._GUIDANCE_KEYS:
            raise ValueError(
                f"Unknown task '{task}'; expected one of {list(self._GUIDANCE_KEYS)}"
            )
        out: dict[str, str] = {}
        for name, spec in self.field_specs.items():
            text = (spec.get("guidance") or {}).get(task)
            if text:
                out[name] = text
        return out

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
            return reduce(operator.or_, (cls._scalar(s) for s in t))
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
