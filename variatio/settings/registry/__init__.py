"""Every setting the installation declares, indexed by key and by name.

The declarations live one module per family and are assembled here in the order `GROUPS`
lays the panel out.
"""

from dataclasses import replace

from ..types import STAGES as PIPELINE_STAGES
from ..types import Setting
from . import builders, generation, inference, logging, reasoning, retrieval, sampling, tunnel

# The one place `variatio` names the tutor, and optional on purpose: `tutor` imports
# `variatio` and never the reverse, so the registry reaches it by name, not by import. Only
# the package being absent switches it off; a tutor whose own import breaks fails loudly.
try:
    from tutor.settings import LANE as TUTOR_LANE
    from tutor.settings import MODEL_KEYS as TUTOR_MODEL_KEYS
    from tutor.settings import READS as TUTOR_READS
    from tutor.settings import SETTINGS as TUTOR_SETTINGS
except ModuleNotFoundError as missing:
    if missing.name not in ("tutor", "tutor.settings"):
        raise
    TUTOR_LANE = None
    TUTOR_MODEL_KEYS: tuple[str, ...] = ()
    TUTOR_READS: tuple[str, ...] = ()
    TUTOR_SETTINGS: list[Setting] = []


def _with_tutor_stage(setting: Setting) -> Setting:
    """Return `setting` with the tutor's stage appended when a turn reads it too."""
    if TUTOR_LANE is None or setting.key not in TUTOR_READS:
        return setting
    return replace(setting, stages=setting.stages + (TUTOR_LANE.key,))


REGISTRY: tuple[Setting, ...] = tuple(
    _with_tutor_stage(setting)
    for setting in inference.SETTINGS
    + tunnel.SETTINGS
    + reasoning.SETTINGS
    + sampling.SETTINGS
    + builders.SETTINGS
    + retrieval.SETTINGS
    + generation.SETTINGS
    + logging.SETTINGS
    + TUTOR_SETTINGS
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
    *(("Tutor",) if TUTOR_LANE else ()),
    "Registro",
)

PIPELINE = reasoning.PIPELINE + ((TUTOR_LANE,) if TUTOR_LANE else ())

# One screen per stage, in the order of the path; the tutor's comes last when it is mounted.
STAGES = PIPELINE_STAGES + ((TUTOR_LANE.key,) if TUTOR_LANE else ())

# The settings outside the pipeline's phases that name a model a call is made with: each gets
# the context cap and the protection every phase model has.
EXTRA_MODEL_KEYS: tuple[str, ...] = TUTOR_MODEL_KEYS

__all__ = [
    "BY_KEY",
    "BY_NAME",
    "EXTRA_MODEL_KEYS",
    "GROUPS",
    "PIPELINE",
    "REGISTRY",
    "STAGES",
]
