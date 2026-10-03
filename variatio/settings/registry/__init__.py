"""Every setting the installation declares, indexed by key and by name.

The declarations live one module per family and are assembled here in the order `GROUPS`
lays the panel out.
"""

from dataclasses import replace

from ..types import STAGES as PIPELINE_STAGES
from ..types import Setting
from . import builders, generation, inference, logging, reasoning, retrieval, sampling, tunnel

# The one place `variatio` names the evaluation and the tutor, and optional on purpose: both
# import `variatio` and never the reverse, so the registry reaches them by name, not by
# import. Only the tutor's package being absent switches the tutor off; a tutor whose own
# import breaks fails loudly.
try:
    from evaluation.settings import LANE as STUDY_LANE
    from evaluation.settings import READS as STUDY_READS
    from evaluation.settings import SETTINGS as STUDY_SETTINGS
except ImportError:
    STUDY_LANE = None
    STUDY_READS: tuple[str, ...] = ()
    STUDY_SETTINGS: list[Setting] = []

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


def _with_reader_stages(setting: Setting) -> Setting:
    """Return `setting` with the study's and the tutor's stages appended when they read it too."""
    stages = setting.stages
    if STUDY_LANE is not None and setting.key in STUDY_READS:
        stages += (STUDY_LANE.key,)
    if TUTOR_LANE is not None and setting.key in TUTOR_READS:
        stages += (TUTOR_LANE.key,)
    return setting if stages == setting.stages else replace(setting, stages=stages)


REGISTRY: tuple[Setting, ...] = tuple(
    _with_reader_stages(setting)
    for setting in inference.SETTINGS
    + tunnel.SETTINGS
    + reasoning.SETTINGS
    + sampling.SETTINGS
    + builders.SETTINGS
    + retrieval.SETTINGS
    + generation.SETTINGS
    + STUDY_SETTINGS
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
    *(("Evaluación",) if STUDY_LANE else ()),
    *(("Tutor",) if TUTOR_LANE else ()),
    "Registro",
)

PIPELINE = (
    reasoning.PIPELINE
    + ((STUDY_LANE,) if STUDY_LANE else ())
    + ((TUTOR_LANE,) if TUTOR_LANE else ())
)

# One screen per stage, in the order of the path; the study's and the tutor's come last, in
# the order of their doors, when they are mounted.
STAGES = (
    PIPELINE_STAGES
    + ((STUDY_LANE.key,) if STUDY_LANE else ())
    + ((TUTOR_LANE.key,) if TUTOR_LANE else ())
)

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
