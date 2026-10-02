"""Every setting the installation declares, indexed by key and by name.

The declarations live one module per family and are assembled here in the order `GROUPS`
lays the panel out.
"""

from ..types import STAGES as PIPELINE_STAGES
from ..types import Setting
from . import builders, generation, inference, logging, reasoning, retrieval, sampling, tunnel

REGISTRY: tuple[Setting, ...] = tuple(
    inference.SETTINGS
    + tunnel.SETTINGS
    + reasoning.SETTINGS
    + sampling.SETTINGS
    + builders.SETTINGS
    + retrieval.SETTINGS
    + generation.SETTINGS
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
    "Registro",
)

PIPELINE = reasoning.PIPELINE

# One screen per stage, in the order of the path.
STAGES = PIPELINE_STAGES

__all__ = ["BY_KEY", "BY_NAME", "GROUPS", "PIPELINE", "REGISTRY", "STAGES"]
