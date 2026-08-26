import json
from pathlib import Path

from loguru import logger

from ..core.json_io import write_json
from ..core.paths import PROJECT_ROOT
from .types import Setting, SettingError, coerce

CONFIG_PATH = PROJECT_ROOT / "config.json"


def nest(flat: dict[str, object]) -> dict:
    out: dict = {}
    for key, value in flat.items():
        parts = key.split(".")
        node = out
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


def _flatten(node: object, prefix: str = "") -> dict[str, object]:
    if not isinstance(node, dict):
        return {prefix: node}
    out: dict[str, object] = {}
    for key, value in node.items():
        child = f"{prefix}.{key}" if prefix else str(key)
        out.update(_flatten(value, child))
    return out


def read_file(path: str | Path) -> dict[str, object]:
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.error(f"[config] No se pudo leer '{path}': {error}")
        return {}
    if not isinstance(raw, dict):
        logger.error(f"[config] '{path}' no contiene un objeto")
        return {}
    return _flatten(raw)


ENGINE_KEY = "engine.name"
PROFILES_KEY = "profiles"

_MISSING = object()


# The engine the file (or the environment) asks for, read BEFORE the general resolution:
# the engine-scoped settings cannot be resolved without knowing which profile to read.
def active_engine(
    settings: list[Setting], file_values: dict[str, object], environ: dict[str, str]
) -> str | None:
    setting = next((s for s in settings if s.key == ENGINE_KEY), None)
    if setting is None:
        return None
    engine = setting.default
    if ENGINE_KEY in file_values:
        try:
            engine = coerce(setting, file_values[ENGINE_KEY])
        except SettingError:
            pass
    if setting.env and environ.get(setting.env, "") != "":
        try:
            engine = coerce(setting, environ[setting.env])
        except SettingError:
            pass
    return str(engine)


def profiles_in(file_values: dict[str, object]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for key, value in file_values.items():
        if not key.startswith(f"{PROFILES_KEY}."):
            continue
        parts = key.split(".", 2)
        if len(parts) < 3:
            continue
        out.setdefault(parts[1], {})[parts[2]] = value
    return out


# default < file < environment. The environment wins because it is the deliberate
# override, and the screen says so instead of letting someone edit a value that will be
# overwritten. An invalid value in the file does not stop the process starting: it warns
# and falls back to the default.
#
# An engine-scoped setting reads its file value from `profiles.<active engine>.<key>` and
# falls back to the bare key, which is where every value lived before the profiles
# existed — so a pre-profile config.json keeps resolving as it always did.
def resolve(
    settings: list[Setting], file_values: dict[str, object], environ: dict[str, str]
) -> tuple[dict[str, object], dict[str, str]]:
    values: dict[str, object] = {}
    sources: dict[str, str] = {}
    engine = active_engine(settings, file_values, environ)
    engines = next(
        (s.choices or () for s in settings if s.key == ENGINE_KEY), ()
    )
    scoped = {setting.key for setting in settings if setting.scope == "engine"}
    known = {setting.key for setting in settings}
    for name in engines:
        known |= {f"{PROFILES_KEY}.{name}.{key}" for key in scoped}

    for key in file_values:
        if key not in known:
            logger.warning(f"[config] Se ignora la clave desconocida «{key}»")

    for setting in settings:
        values[setting.key] = setting.default_for(engine)
        sources[setting.key] = "default"

        file_value = _MISSING
        if setting.scope == "engine" and engine:
            file_value = file_values.get(f"{PROFILES_KEY}.{engine}.{setting.key}", _MISSING)
        if file_value is _MISSING:
            file_value = file_values.get(setting.key, _MISSING)
        if file_value is not _MISSING:
            try:
                values[setting.key] = coerce(setting, file_value)
                sources[setting.key] = "file"
            except SettingError as error:
                logger.warning(f"[config] En el fichero, {error}; se usa el valor por defecto")

        if setting.env and environ.get(setting.env, "") != "":
            try:
                values[setting.key] = coerce(setting, environ[setting.env])
                sources[setting.key] = "env"
            except SettingError as error:
                logger.warning(f"[config] En el entorno, {error}; se usa el valor anterior")

    return values, sources


def validate_patch(settings: list[Setting], patch: dict[str, object]) -> dict[str, object]:
    by_key = {setting.key: setting for setting in settings}
    out: dict[str, object] = {}
    errors: list[str] = []
    for key, raw in patch.items():
        setting = by_key.get(key)
        if setting is None:
            errors.append(f"«{key}» no es un ajuste conocido")
            continue
        if not setting.editable:
            errors.append(f"'{setting.name or setting.key}' no se puede cambiar en caliente")
            continue
        try:
            out[key] = coerce(setting, raw)
        except SettingError as error:
            errors.append(str(error))
    if errors:
        raise SettingError("; ".join(errors))
    return out


# The global settings are written at the top level, as always; the engine-scoped ones live
# under `profiles.<engine>` and are handed in already keyed by engine, so a write for one
# profile never touches what another has saved. With `profiles=None` (or no engine-scoped
# setting declared) the shape is exactly what it was before profiles existed.
def write_file(
    path: str | Path,
    settings: list[Setting],
    values: dict[str, object],
    profiles: dict[str, dict[str, object]] | None = None,
) -> Path:
    scoped = {setting.key for setting in settings if setting.scope == "engine"}
    secret = {setting.key for setting in settings if setting.secret}
    public = {
        setting.key: values[setting.key]
        for setting in settings
        if not setting.secret and setting.key in values and setting.key not in scoped
    }
    tree = nest(public)
    if profiles:
        tree[PROFILES_KEY] = {
            engine: nest({key: value for key, value in section.items() if key not in secret})
            for engine, section in sorted(profiles.items())
            if section
        }
    return write_json(path, tree)
