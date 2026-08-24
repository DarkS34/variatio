from dataclasses import dataclass
from enum import Enum

TRUTHY = ("1", "true", "yes", "on", "sí", "si")


# What has to happen for a change to this setting to be real. It is what lets the panel
# say «esto va a re-embeber el índice» BEFORE saving instead of twenty minutes later.
class Impact(str, Enum):
    NONE = "none"
    ENGINE = "engine"
    CONTEXTS = "contexts"
    REINDEX = "reindex"
    LOCKED = "locked"


KINDS = ("str", "int", "float", "bool", "list[str]", "dict[str,int]")

SCOPES = ("global", "engine")


class SettingError(ValueError):
    pass


@dataclass(frozen=True)
class Setting:
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
    scope: str = "global"
    engine_defaults: tuple[tuple[str, object], ...] | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise SettingError(f"'{self.name or self.key}': tipo desconocido '{self.kind}'")
        if self.scope not in SCOPES:
            raise SettingError(f"'{self.name or self.key}': ámbito desconocido '{self.scope}'")
        if not self.doc.strip():
            raise SettingError(f"'{self.name or self.key}': falta la documentación")

    def default_for(self, engine: str | None) -> object:
        if engine and self.engine_defaults:
            for name, value in self.engine_defaults:
                if name == engine:
                    return value
        return self.default


def coerce(setting: Setting, raw: object) -> object:
    if raw is None:
        if setting.nullable:
            return None
        raise SettingError(f"'{setting.name or setting.key}' no admite un valor vacío")
    value = _canonical(setting, _convert(setting, raw))
    _check(setting, value)
    return value


# A `choices` list is a closed vocabulary, so it is matched without regard to case and the
# declared spelling is what comes back. This is what keeps `VG_LOG_LEVEL=debug` working the
# way `config.LOG_LEVEL`'s `.upper()` used to make it work.
def _canonical(setting: Setting, value: object) -> object:
    if not setting.choices or not isinstance(value, str):
        return value
    for choice in setting.choices:
        if isinstance(choice, str) and choice.lower() == value.lower():
            return choice
    return value


def _convert(setting: Setting, raw: object) -> object:
    kind = setting.kind
    label = setting.name or setting.key
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in TRUTHY
    if kind == "int":
        return _number(setting, raw, int)
    if kind == "float":
        return _number(setting, raw, float)
    if kind == "list[str]":
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        if isinstance(raw, (list, tuple)):
            return [str(part) for part in raw]
        raise SettingError(f"'{label}' espera una lista, no {type(raw).__name__}")
    if kind == "dict[str,int]":
        if not isinstance(raw, dict):
            raise SettingError(f"'{label}' espera un objeto, no {type(raw).__name__}")
        return {str(key): _number(setting, item, int) for key, item in raw.items()}
    if isinstance(raw, (dict, list, tuple, bool)):
        raise SettingError(f"'{label}' espera un texto, no {type(raw).__name__}")
    return str(raw)


def _number(setting: Setting, raw: object, cast):
    if isinstance(raw, bool):
        raise SettingError(f"'{setting.name or setting.key}': «{raw}» no es un número válido")
    try:
        return cast(raw)
    except (TypeError, ValueError):
        raise SettingError(
            f"'{setting.name or setting.key}': «{raw}» no es un número válido"
        ) from None


def _check(setting: Setting, value: object) -> None:
    label = setting.name or setting.key
    if setting.choices and value not in setting.choices:
        options = ", ".join(str(choice) for choice in setting.choices)
        raise SettingError(f"'{label}': «{value}» no está entre {options}")
    if setting.minimum is not None and value < setting.minimum:
        raise SettingError(f"'{label}': {value} está por debajo de {setting.minimum}")
    if setting.maximum is not None and value > setting.maximum:
        raise SettingError(f"'{label}': {value} está por encima de {setting.maximum}")
