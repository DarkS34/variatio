"""Every setting the installation declares, indexed by key and by name.

The declarations live one module per family and are assembled here in the order `GROUPS`
lays the panel out.
"""

from ..types import Setting
from . import builders, generation, inference, logging, reasoning, retrieval, tunnel

# The one place `variatio` names the evaluation, and optional on purpose: `evaluation` imports
# `variatio` and never the reverse, so the registry reaches it by name, not by import.
try:
    from evaluation.settings import SETTINGS as STUDY_SETTINGS
except ImportError:
    STUDY_SETTINGS: list[Setting] = []

REGISTRY: tuple[Setting, ...] = tuple(
    inference.SETTINGS
    + tunnel.SETTINGS
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
    "Túnel SSH",
    "Modelos",
    "Modelos generadores",
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
