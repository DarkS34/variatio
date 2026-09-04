"""The study's own index of settings, resolved on every read.

The annotations below are the readable index, exactly as `variatio.config`'s are; the
values are declared in `study/settings.py` and derived here.
"""

import os

from variatio import config as pipeline_config
from variatio import settings

EXTERNAL_PROVIDERS: list[str]
LOCAL_MODEL: str
PROVIDER_MODELS: dict[str, str]
PROVIDER_KEYS: dict[str, str]
EXTERNAL_TIMEOUT: float

# The rag arm's own design, not a knob: how the raw documents are cut and how many pieces of
# each slot the prompt carries. Three and three — six pieces of ~1 500 characters — is the
# order of what the system's few-shot block costs (`MAX_FEW_SHOT_EXAMPLES` whole exemplars),
# so the two arms differ by what they were given and not by how much.
RAG_CHUNK_CHARS = 1500
RAG_TOP_K_THEORY = 3
RAG_TOP_K_EXERCISES = 3


def _chain(declared) -> list[str]:
    """Normalise the declared provider chain: lowercased, deduplicated, `none` dropped."""
    chain: list[str] = []
    for name in declared:
        name = str(name).strip().lower()
        if name and name != "none" and name not in chain:
            chain.append(name)
    return chain


def _by_provider(values: dict[str, object], prefix: str) -> dict[str, str]:
    """Index every `<prefix><provider>` setting by its provider name.

    Read off the registry rather than listed here, so a fourth provider is two settings
    and one caller in `arms/external.py` — never a third place holding the same names,
    which is where a key and a model id from different providers would start to cross.
    """
    return {k[len(prefix) :]: str(v) for k, v in values.items() if k.startswith(prefix)}


def derive(values: dict[str, object], environ: dict[str, str]) -> dict[str, object]:
    """Compute the study's five resolved values from the registry and the environment."""
    providers = _chain(values["evaluation.providers"])
    models = _by_provider(values, "evaluation.models.")
    keys = _by_provider(values, "evaluation.keys.")

    # The legacy single-provider pair moves TOGETHER onto the head of the chain: a key and
    # a model id from different providers is precisely the mix-up this prevents.
    legacy = environ.get("EVAL_EXTERNAL_API_KEY", "")
    first = providers[0] if providers else ""
    if legacy and first in keys and not keys[first]:
        keys[first] = legacy
        models[first] = environ.get("EVAL_EXTERNAL_MODEL_ID", "") or models[first]

    return {
        # The writer of the two local arms: the installation's own choice, or — with none —
        # the same model that writes a generation, which is what every session before the
        # setting existed ran with.
        "LOCAL_MODEL": str(values.get("evaluation.local_model") or "")
        or pipeline_config.VARIANT_GENERATION_LLM,
        "EXTERNAL_PROVIDERS": providers,
        "PROVIDER_MODELS": models,
        "PROVIDER_KEYS": keys,
        "EXTERNAL_TIMEOUT": values["evaluation.timeout"],
    }


def __getattr__(name: str):
    """Resolve one of the annotated names above, freshly, on every read.

    `settings.reload()` rewrites `variatio.config`'s globals through the namespace it was
    handed and this module is not that namespace, so caching here would serve the value the
    panel just replaced.
    """
    values = derive(settings.values(), dict(os.environ))
    if name in values:
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
