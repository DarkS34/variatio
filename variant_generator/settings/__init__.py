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


def update(patch: dict[str, object]) -> set[Impact]:
    coerced = store.validate_patch(list(REGISTRY), patch)
    merged = dict(_values)
    merged.update(coerced)
    store.write_file(store.CONFIG_PATH, list(REGISTRY), merged)
    changed = {key for key, value in coerced.items() if _values.get(key) != value}
    load()
    if _namespace is not None:
        _write(_namespace)
    for key in sorted(changed):
        logger.info(f"[config] «{key}» cambiado")
    return {BY_KEY[key].impact for key in changed} - {Impact.NONE, Impact.LOCKED}


def snapshot() -> list[dict]:
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
        }
        if setting.secret:
            row["state"] = "configurada" if _values.get(setting.key) else "ausente"
        else:
            row["value"] = _values.get(setting.key)
            row["default"] = setting.default
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
    "snapshot",
    "sources",
    "update",
    "values",
]
