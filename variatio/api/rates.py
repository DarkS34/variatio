"""How long one unit of a construction step takes, per engine and model (D-241).

The seconds are measured, not modelled: `rates/<engine>.json` at the project root, versioned
beside `config.json`, one file per inference engine. A step's rate is published only when
every phase whose model the step calls names the model it was measured with, so a model
changed in the panel (the case D-156 was about) or an engine with no file shows no time.
"""

import json

from ..utils.paths import PROJECT_ROOT
from ..settings import engine_profile
from ..settings.derived import PHASES

RATES_DIR = PROJECT_ROOT / "rates"

# The phases whose model each measured step calls: the step's time is theirs.
STEP_PHASES = {
    "transcribe_pages": ("transcribe", "transcribe_seam"),
    "kg_extract": ("kg_extract",),
    "kg_merge": ("kg_clean_merge",),
    "kg_drop": ("kg_clean_drop",),
    "kg_link": ("kg_link_domain", "kg_link_cross_domain"),
    "descriptions": ("description_generation",),
    "scan": ("ep_scan",),
    "bank_batches": ("eb_extract",),
    "taggability": ("kg_taggable",),
    "tagging": ("concept_tagger",),
}


def step_rates() -> dict[str, dict]:
    """Return `{step: {"unit", "seconds"}}` for the steps measured on today's engine and models."""
    try:
        measured = json.loads((RATES_DIR / f"{engine_profile().engine}.json").read_text())["steps"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    rates = {}
    for step, phases in STEP_PHASES.items():
        models = {_model(phase) for phase in phases}
        entry = measured.get(step) or {}
        seconds = (entry.get("seconds") or {}).get(models.pop()) if len(models) == 1 else None
        if isinstance(seconds, (int, float)) and seconds > 0:
            rates[step] = {"unit": entry.get("unit"), "seconds": float(seconds)}
    return rates


def _model(phase: str) -> str:
    """Return the model a pipeline phase is configured with right now."""
    return str(getattr(engine_profile(), PHASES[f"models.phases.{phase}"]))
