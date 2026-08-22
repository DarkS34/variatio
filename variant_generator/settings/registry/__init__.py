from ..types import Setting
from . import builders, evaluation, generation, inference, logging, retrieval

REGISTRY: tuple[Setting, ...] = tuple(
    inference.SETTINGS
    + builders.SETTINGS
    + retrieval.SETTINGS
    + generation.SETTINGS
    + evaluation.SETTINGS
    + logging.SETTINGS
)

BY_KEY = {setting.key: setting for setting in REGISTRY}
BY_NAME = {setting.name: setting for setting in REGISTRY if setting.name}

# The order the panel lays its blocks out in.
GROUPS = (
    "Motor",
    "Modelos",
    "Muestreo",
    "Ventana de contexto",
    "Constructores",
    "Recuperación",
    "Etiquetado y generación",
    "Evaluación",
    "Registro",
)

__all__ = ["BY_KEY", "BY_NAME", "GROUPS", "REGISTRY"]
