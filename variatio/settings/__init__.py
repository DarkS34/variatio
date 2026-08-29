"""The installation's settings: resolve them, hand them to `config`, and write them back."""

import os

from loguru import logger

from . import derived, store
from .registry import BY_KEY, BY_NAME, GROUPS, PIPELINE, REGISTRY
from .types import Impact, Setting, SettingError

_values: dict[str, object] = {}
_sources: dict[str, str] = {}
_namespace: dict | None = None


def values() -> dict[str, object]:
    """Return every resolved value, keyed by setting key."""
    return dict(_values)


def sources() -> dict[str, str]:
    """Return which layer supplied each value: default, file or env."""
    return dict(_sources)


def load() -> None:
    """Resolve every setting from the registry, `config.json` and the environment."""
    global _values, _sources
    _values, _sources = store.resolve(
        list(REGISTRY), store.read_file(store.CONFIG_PATH), dict(os.environ)
    )


def apply(namespace: dict) -> None:
    """Resolve everything into `config.py`'s own globals, of which this is the only writer.

    Keeping the namespace lets a later reload reach the same module without importing it
    back, which would be a cycle: `config` imports this.
    """
    global _namespace
    _namespace = namespace
    load()
    _write(namespace)


def _write(namespace: dict) -> None:
    """Write the named settings and everything derived into a namespace."""
    for setting in REGISTRY:
        if setting.name:
            namespace[setting.name] = _values[setting.key]
    namespace.update(derived.derive(_values))


def _reload_keeping_previous() -> dict[str, object]:
    """Re-resolve everything into the namespace and return the values from before."""
    before = dict(_values)
    load()
    if _namespace is not None:
        _write(_namespace)
    return before


def _impacts(changed: set[str]) -> set[Impact]:
    """Return what the changed settings oblige the caller to invalidate."""
    return {BY_KEY[key].impact for key in changed} - {Impact.NONE, Impact.LOCKED}


def reload() -> set[Impact]:
    """Re-read the file and the environment, returning what that obliges."""
    before = _reload_keeping_previous()
    changed = {key for key in _values if _values[key] != before.get(key)}
    logger.info(f"[config] Reloaded: {len(changed)} setting(s) changed")
    return _impacts(changed)


def active_engine() -> str | None:
    """Return the engine whose profile the engine-scoped settings resolve from."""
    value = _values.get(store.ENGINE_KEY)
    return str(value) if value else None


def _stored_profiles(flat: dict[str, object], engine: str | None) -> dict[str, dict[str, object]]:
    """Return the stored per-engine sections, folding any pre-profile top-level value in.

    Without that fold, the first write of an old file would drop the values it holds.
    """
    profiles = store.profiles_in(flat)
    if engine:
        section = profiles.setdefault(engine, {})
        for key, value in flat.items():
            if key in BY_KEY and BY_KEY[key].scope == "engine":
                section.setdefault(key, value)
    return profiles


def _globals_after(coerced: dict[str, object]) -> dict[str, object]:
    """Return the global settings as they stand once the patch is applied."""
    merged = {key: value for key, value in _values.items() if BY_KEY[key].scope == "global"}
    merged.update(
        {key: value for key, value in coerced.items() if BY_KEY[key].scope == "global"}
    )
    return merged


def update(patch: dict[str, object]) -> set[Impact]:
    """Save a patch and re-resolve, returning what the change obliges the caller to redo.

    The engine-scoped keys are written into the profile of the engine the patch leaves
    active, and only there: the other profiles travel through the write untouched.
    """
    coerced = store.validate_patch(list(REGISTRY), patch)
    flat = store.read_file(store.CONFIG_PATH)
    profiles = _stored_profiles(flat, active_engine())
    target = str(coerced.get(store.ENGINE_KEY) or active_engine() or "") or None
    scoped = {key: value for key, value in coerced.items() if BY_KEY[key].scope == "engine"}
    if scoped and target:
        profiles.setdefault(target, {}).update(scoped)
    store.write_file(store.CONFIG_PATH, list(REGISTRY), _globals_after(coerced), profiles)
    changed = {key for key, value in coerced.items() if _values.get(key) != value}
    before = _reload_keeping_previous()
    changed |= {key for key in _values if _values[key] != before.get(key)}
    for key in sorted(changed):
        logger.info(f"[config] «{key}» changed")
    return _impacts(changed)


def _refuse_unresettable(keys: list[str]) -> None:
    """Raise SettingError when a key is not declared, or cannot be changed hot."""
    unknown = [key for key in keys if key not in BY_KEY]
    if unknown:
        raise SettingError(f"Ajustes desconocidos: {', '.join(unknown)}")
    locked = [key for key in keys if not BY_KEY[key].editable]
    if locked:
        raise SettingError(f"No se pueden cambiar en caliente: {', '.join(locked)}")


def reset(keys: list[str]) -> set[Impact]:
    """Remove keys from `config.json`, which is the only way a row reads «por defecto» again."""
    _refuse_unresettable(keys)
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
    before = _reload_keeping_previous()
    changed = {key for key in keys if _values.get(key) != before.get(key)}
    for key in sorted(changed):
        logger.info(f"[config] «{key}» back to its default")
    return _impacts(changed)


def snapshot() -> list[dict]:
    """Return every setting as the panel reads it; a secret reports only whether it is set."""
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
    """Serialise the reasoning pipeline: one lane per column, one phase per model call."""
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
                    "effort": phase.effort,
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
