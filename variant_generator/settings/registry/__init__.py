from ..types import Setting
from . import builders, generation, inference, logging, reasoning, retrieval

# The study declares its own block and lives outside this package: `study` imports
# `variant_generator` and never the reverse, so the registry reaches it by name rather
# than by import direction. Without the study installed the panel simply shows one group
# fewer, and `config.json` round-trips one section fewer.
try:
    from study.settings import SETTINGS as STUDY_SETTINGS
except ImportError:
    STUDY_SETTINGS: list[Setting] = []

REGISTRY: tuple[Setting, ...] = tuple(
    inference.SETTINGS
    + reasoning.SETTINGS
    + builders.SETTINGS
    + retrieval.SETTINGS
    + generation.SETTINGS
    + STUDY_SETTINGS
    + logging.SETTINGS
)

BY_KEY = {setting.key: setting for setting in REGISTRY}
BY_NAME = {setting.name: setting for setting in REGISTRY if setting.name}

# The order the panel lays its blocks out in.
GROUPS = (
    "Motor",
    "Modelos",
    "Razonamiento",
    "Muestreo",
    "Ventana de contexto",
    "Constructores",
    "Recuperación",
    "Etiquetado y generación",
    "Evaluación",
    "Registro",
)

PIPELINE = reasoning.PIPELINE

__all__ = ["BY_KEY", "BY_NAME", "GROUPS", "PIPELINE", "REGISTRY"]
