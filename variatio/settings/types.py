"""What a setting is: its declaration, and the coercion of a raw value into it."""

from dataclasses import dataclass
from enum import Enum

TRUTHY = ("1", "true", "yes", "on", "sí", "si")


class Impact(str, Enum):
    """What has to be invalidated for a change to this setting to be real.

    It is what lets the panel warn that saving will re-embed the index before the save
    rather than twenty minutes later.
    """

    NONE = "none"
    ENGINE = "engine"
    CONTEXTS = "contexts"
    REINDEX = "reindex"
    LOCKED = "locked"


KINDS = ("str", "int", "float", "bool", "list[str]", "dict[str,int]")

SCOPES = ("global", "engine")


class SettingError(ValueError):
    """A setting was declared wrongly, or a value does not fit the one it is meant for."""


@dataclass(frozen=True)
class Setting:
    """One declared setting: its value, its type, its measured documentation and its cost.

    `name` is the `config` attribute it becomes; an empty one is read by `derived` alone.
    A `scope="engine"` setting resolves from `profiles.<engine>` rather than the top level.
    """

    key: str
    name: str
    kind: str
    default: object
    group: str
    doc: str
    impact: Impact
    env: str | None = None
    editable: bool = True
    secret: bool = False
    nullable: bool = False
    choices: tuple | None = None
    minimum: float | None = None
    maximum: float | None = None
    min_items: int | None = None
    scope: str = "global"
    engine_defaults: tuple[tuple[str, object], ...] | None = None

    def __post_init__(self) -> None:
        """Raise SettingError when the declaration itself is malformed."""
        if self.kind not in KINDS:
            raise SettingError(f"'{self.name or self.key}': tipo desconocido '{self.kind}'")
        if self.scope not in SCOPES:
            raise SettingError(f"'{self.name or self.key}': ámbito desconocido '{self.scope}'")
        if not self.doc.strip():
            raise SettingError(f"'{self.name or self.key}': falta la documentación")

    def default_for(self, engine: str | None) -> object:
        """Return this setting's default under `engine`, which may declare its own."""
        if engine and self.engine_defaults:
            for name, value in self.engine_defaults:
                if name == engine:
                    return value
        return self.default


def coerce(setting: Setting, raw: object) -> object:
    """Convert a raw file or environment value into the setting's type, or raise."""
    if raw is None:
        if setting.nullable:
            return None
        raise SettingError(f"'{setting.name or setting.key}' no admite un valor vacío")
    value = _canonical(setting, _convert(setting, raw))
    _check(setting, value)
    return value


def _canonical(setting: Setting, value: object) -> object:
    """Return the declared spelling of a `choices` value, matched without regard to case.

    A closed vocabulary is matched case-insensitively so `VARIATIO_LOG_LEVEL=debug` resolves,
    and what comes back is the spelling the registry declared.
    """
    if not setting.choices or not isinstance(value, str):
        return value
    for choice in setting.choices:
        if isinstance(choice, str) and choice.lower() == value.lower():
            return choice
    return value


def _convert(setting: Setting, raw: object) -> object:
    """Cast a raw value to the setting's declared kind, or raise SettingError."""
    kind = setting.kind
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in TRUTHY
    if kind == "int":
        return _number(setting, raw, int)
    if kind == "float":
        return _number(setting, raw, float)
    if kind == "list[str]":
        return _string_list(setting, raw)
    if kind == "dict[str,int]":
        return _int_map(setting, raw)
    if isinstance(raw, (dict, list, tuple, bool)):
        label = setting.name or setting.key
        raise SettingError(f"'{label}' espera un texto, no {type(raw).__name__}")
    return str(raw)


def _string_list(setting: Setting, raw: object) -> list[str]:
    """Cast to a list of strings, splitting a comma-separated string and dropping blanks."""
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(part) for part in raw]
    label = setting.name or setting.key
    raise SettingError(f"'{label}' espera una lista, no {type(raw).__name__}")


def _int_map(setting: Setting, raw: object) -> dict[str, int]:
    """Cast to a mapping of strings to integers."""
    if not isinstance(raw, dict):
        label = setting.name or setting.key
        raise SettingError(f"'{label}' espera un objeto, no {type(raw).__name__}")
    return {str(key): _number(setting, item, int) for key, item in raw.items()}


def _number(setting: Setting, raw: object, cast):
    """Cast to a number, refusing a bool — which Python would otherwise accept as 0 or 1."""
    if isinstance(raw, bool):
        raise SettingError(f"'{setting.name or setting.key}': «{raw}» no es un número válido")
    try:
        return cast(raw)
    except (TypeError, ValueError):
        raise SettingError(
            f"'{setting.name or setting.key}': «{raw}» no es un número válido"
        ) from None


def _check(setting: Setting, value: object) -> None:
    """Raise SettingError when the converted value falls outside what was declared."""
    label = setting.name or setting.key
    if setting.choices and value not in setting.choices:
        options = ", ".join(str(choice) for choice in setting.choices)
        raise SettingError(f"'{label}': «{value}» no está entre {options}")
    if setting.min_items is not None and len(value) < setting.min_items:
        raise SettingError(
            f"'{label}': hacen falta al menos {setting.min_items}, y llegan {len(value)}"
        )
    if setting.minimum is not None and value < setting.minimum:
        raise SettingError(f"'{label}': {value} está por debajo de {setting.minimum}")
    if setting.maximum is not None and value > setting.maximum:
        raise SettingError(f"'{label}': {value} está por encima de {setting.maximum}")
