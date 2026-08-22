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


# default < file < environment. The environment wins because it is the deliberate
# override, and the screen says so instead of letting someone edit a value that will be
# overwritten. An invalid value in the file does not stop the process starting: it warns
# and falls back to the default.
def resolve(
    settings: list[Setting], file_values: dict[str, object], environ: dict[str, str]
) -> tuple[dict[str, object], dict[str, str]]:
    values: dict[str, object] = {}
    sources: dict[str, str] = {}
    known = {setting.key for setting in settings}

    for key in file_values:
        if key not in known:
            logger.warning(f"[config] Se ignora la clave desconocida «{key}»")

    for setting in settings:
        values[setting.key] = setting.default
        sources[setting.key] = "default"

        if setting.key in file_values:
            try:
                values[setting.key] = coerce(setting, file_values[setting.key])
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


def write_file(path: str | Path, settings: list[Setting], values: dict[str, object]) -> Path:
    public = {
        setting.key: values[setting.key]
        for setting in settings
        if not setting.secret and setting.key in values
    }
    return write_json(path, nest(public))
