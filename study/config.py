import os

from variatio import config as pipeline
from variatio import settings

EXTERNAL_PROVIDERS: list[str]
PROVIDER_MODELS: dict[str, str]
PROVIDER_KEYS: dict[str, str]
EXTERNAL_TIMEOUT: float
RAG_TOP_K: int


def _chain(declared) -> list[str]:
    chain: list[str] = []
    for name in declared:
        name = str(name).strip().lower()
        if name and name != "none" and name not in chain:
            chain.append(name)
    return chain


def derive(
    values: dict[str, object], environ: dict[str, str], few_shot: int
) -> dict[str, object]:
    providers = _chain(values["evaluation.providers"])
    models = {
        "gemini": values["evaluation.models.gemini"],
        "groq": values["evaluation.models.groq"],
    }
    keys = {
        "gemini": values["evaluation.keys.gemini"],
        "groq": values["evaluation.keys.groq"],
    }

    # An environment still exporting the old single-provider pair keeps working. The pair
    # moves TOGETHER onto whichever provider the chain leads with, because a key and a
    # model id from different providers is precisely the mix-up this prevents.
    legacy = environ.get("EVAL_EXTERNAL_API_KEY", "")
    first = providers[0] if providers else ""
    if legacy and first in keys and not keys[first]:
        keys[first] = legacy
        models[first] = environ.get("EVAL_EXTERNAL_MODEL_ID", "") or models[first]

    return {
        "EXTERNAL_PROVIDERS": providers,
        "PROVIDER_MODELS": models,
        "PROVIDER_KEYS": keys,
        "EXTERNAL_TIMEOUT": values["evaluation.timeout"],
        # The rag arm retrieves as many exemplars as the system's few-shot budget allows,
        # so the two differ by the graph and not by how much of the bank they saw.
        "RAG_TOP_K": few_shot,
    }


# Resolved on every read rather than written into the module once. `settings.reload()`
# rewrites `variatio.config`'s globals through the namespace it was handed, and
# this module is not that namespace: caching here would serve the value the panel just
# replaced. The annotations above stay the readable index, as in `variatio`.
def __getattr__(name: str):
    values = derive(settings.values(), dict(os.environ), pipeline.MAX_FEW_SHOT_EXAMPLES)
    if name in values:
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
