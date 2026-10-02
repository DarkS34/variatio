"""Every setting the installation declares, indexed by key and by name.

The declarations live one module per family and are assembled here in the order `GROUPS`
lays the panel out.
"""

from dataclasses import replace

from ..types import STAGES as PIPELINE_STAGES
from ..types import Setting
from . import builders, generation, inference, logging, reasoning, retrieval, tunnel

# The one place `variatio` names the evaluation, and optional on purpose: `evaluation` imports
# `variatio` and never the reverse, so the registry reaches it by name, not by import.
try:
    from evaluation.settings import LANE as STUDY_LANE
    from evaluation.settings import READS as STUDY_READS
    from evaluation.settings import SETTINGS as STUDY_SETTINGS
except ImportError:
    STUDY_LANE = None
    STUDY_READS: tuple[str, ...] = ()
    STUDY_SETTINGS: list[Setting] = []


def _with_study_stage(setting: Setting) -> Setting:
    """Return `setting` with the study's stage appended when a session reads it too."""
    if STUDY_LANE is None or setting.key not in STUDY_READS:
        return setting
    return replace(setting, stages=setting.stages + (STUDY_LANE.key,))


REGISTRY: tuple[Setting, ...] = tuple(
    _with_study_stage(setting)
    for setting in inference.SETTINGS
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

PIPELINE = reasoning.PIPELINE + ((STUDY_LANE,) if STUDY_LANE else ())

# One screen per stage, in the order of the path; the study's comes last when it is mounted.
STAGES = PIPELINE_STAGES + ((STUDY_LANE.key,) if STUDY_LANE else ())

__all__ = ["BY_KEY", "BY_NAME", "GROUPS", "PIPELINE", "REGISTRY", "STAGES"]
