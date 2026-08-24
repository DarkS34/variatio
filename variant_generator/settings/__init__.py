import os

from loguru import logger

from . import derived, store
from .registry import BY_KEY, BY_NAME, GROUPS, PIPELINE, REGISTRY
from .types import Impact, Setting, SettingError

_values: dict[str, object] = {}
_sources: dict[str, str] = {}
_namespace: dict | None = None


def values() -> dict[str, object]:
    return dict(_values)


def sources() -> dict[str, str]:
    return dict(_sources)


def load() -> None:
    global _values, _sources
    _values, _sources = store.resolve(
        list(REGISTRY), store.read_file(store.CONFIG_PATH), dict(os.environ)
    )


# `config.py` hands its own globals in, and this is the only writer of them. Keeping the
# namespace lets a later reload reach the same module without importing it back — which
# would be a cycle, since config imports this.
def apply(namespace: dict) -> None:
    global _namespace
    _namespace = namespace
    load()
    _write(namespace)


def _write(namespace: dict) -> None:
    for setting in REGISTRY:
        if setting.name:
            namespace[setting.name] = _values[setting.key]
    namespace.update(derived.derive(_values))


def reload() -> set[Impact]:
    before = dict(_values)
    load()
    if _namespace is not None:
        _write(_namespace)
    changed = {key for key in _values if _values[key] != before.get(key)}
    logger.info(f"[config] Recargado: {len(changed)} ajuste(s) cambiaron")
    return {BY_KEY[key].impact for key in changed} - {Impact.NONE, Impact.LOCKED}


def active_engine() -> str | None:
    value = _values.get(store.ENGINE_KEY)
    return str(value) if value else None


# The stored per-engine sections, with any pre-profile top-level value folded into the
# active profile so the first write migrates an old file instead of dropping its values.
def _stored_profiles(flat: dict[str, object], engine: str | None) -> dict[str, dict[str, object]]:
    profiles = store.profiles_in(flat)
    if engine:
        section = profiles.setdefault(engine, {})
        for key, value in flat.items():
            if key in BY_KEY and BY_KEY[key].scope == "engine":
                section.setdefault(key, value)
    return profiles


# A patch writes its engine-scoped keys into the profile of the engine the patch leaves
# active, and only those: the other profiles travel through the write untouched, which is
# what lets each engine keep its own saved configuration.
def update(patch: dict[str, object]) -> set[Impact]:
    coerced = store.validate_patch(list(REGISTRY), patch)
    flat = store.read_file(store.CONFIG_PATH)
    profiles = _stored_profiles(flat, active_engine())
    target = str(coerced.get(store.ENGINE_KEY) or active_engine() or "") or None
    scoped = {key: value for key, value in coerced.items() if BY_KEY[key].scope == "engine"}
    if scoped and target:
        profiles.setdefault(target, {}).update(scoped)
    merged = {key: value for key, value in _values.items() if BY_KEY[key].scope == "global"}
    merged.update(
        {key: value for key, value in coerced.items() if BY_KEY[key].scope == "global"}
    )
    store.write_file(store.CONFIG_PATH, list(REGISTRY), merged, profiles)
    changed = {key for key, value in coerced.items() if _values.get(key) != value}
    before = dict(_values)
    load()
    if _namespace is not None:
        _write(_namespace)
    changed |= {key for key in _values if _values[key] != before.get(key)}
    for key in sorted(changed):
        logger.info(f"[config] «{key}» cambiado")
    return {BY_KEY[key].impact for key in changed} - {Impact.NONE, Impact.LOCKED}


def reset(keys: list[str]) -> set[Impact]:
    unknown = [key for key in keys if key not in BY_KEY]
    if unknown:
        raise SettingError(f"Ajustes desconocidos: {', '.join(unknown)}")
    locked = [key for key in keys if not BY_KEY[key].editable]
    if locked:
        raise SettingError(f"No se pueden cambiar en caliente: {', '.join(locked)}")
    engine = active_engine()
    flat = store.read_file(store.CONFIG_PATH)
    profiles = _stored_profiles(flat, engine)
    for key in keys:
        if BY_KEY[key].scope == "engine" and engine:
            profiles.get(engine, {}).pop(key, None)
    kept = {
        key: value
        for key, value in flat.items()
        if key not in keys and key in BY_KEY and BY_KEY[key].scope == "global"
    }
    store.write_file(store.CONFIG_PATH, list(REGISTRY), kept, profiles)
    before = dict(_values)
    load()
    if _namespace is not None:
        _write(_namespace)
    changed = {key for key in keys if _values.get(key) != before.get(key)}
    for key in sorted(changed):
        logger.info(f"[config] «{key}» devuelto a su valor por defecto")
    return {BY_KEY[key].impact for key in changed} - {Impact.NONE, Impact.LOCKED}


def snapshot() -> list[dict]:
    engine = active_engine()
    out = []
    for setting in REGISTRY:
        row = {
            "key": setting.key,
            "name": setting.name,
            "kind": setting.kind,
            "group": setting.group,
            "doc": setting.doc,
            "impact": setting.impact.value,
            "editable": setting.editable and setting.impact is not Impact.LOCKED,
            "source": _sources.get(setting.key, "default"),
            "env": setting.env,
            "choices": list(setting.choices) if setting.choices else None,
            "minimum": setting.minimum,
            "maximum": setting.maximum,
            "nullable": setting.nullable,
            "secret": setting.secret,
            "scope": setting.scope,
        }
        if setting.secret:
            row["state"] = "configurada" if _values.get(setting.key) else "ausente"
        else:
            row["value"] = _values.get(setting.key)
            row["default"] = setting.default_for(engine)
        out.append(row)
    return out


def pipeline() -> list[dict]:
    return [
        {
            "key": lane.key,
            "label": lane.label,
            "phases": [
                {
                    "key": phase.key,
                    "label": phase.label,
                    "model": phase.model,
                    "setting": phase.setting,
                    "fixed": phase.fixed,
                    "note": phase.note,
                }
                for phase in lane.phases
            ],
        }
        for lane in PIPELINE
    ]


__all__ = [
    "GROUPS",
    "Impact",
    "PIPELINE",
    "REGISTRY",
    "Setting",
    "SettingError",
    "apply",
    "pipeline",
    "reload",
    "reset",
    "snapshot",
    "sources",
    "update",
    "values",
]
