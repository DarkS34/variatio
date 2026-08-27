"""Which backend each job kind competes for, so two of them can run at once.

There are two scarce things behind this queue and they are not the same thing. Ollama
serves from one GPU, so two local jobs would only swap weights; Cerebras serves over the
network under a rolling quota, so two remote jobs would only race for the same budget.
But a local job and a remote one contend for nothing at all, and until now one waited for
the other for no reason.

A lane is reserved by the GENERATIVE models a job kind calls. The embedder and the
guardrail are deliberately outside the count: both are small, both stay on Ollama whatever
the engine is, and the three co-reside — they are not what the wait is about. What that
buys is that a job whose generative work is remote reserves only `REMOTE`, even though it
still embeds locally all the way through.

Everything is read through `config.<NAME>` at the moment a job is queued, never cached
here: the engine is switched from the panel while the process runs.
"""

from loguru import logger

from variatio import config, stages
from variatio.core import inference

LOCAL = "local"
REMOTE = "remote"

BACKENDS = (LOCAL, REMOTE)

# A build's models are the builder's own declaration, so the phases and the lane cannot
# drift apart: `stages.build_models` is the same list `warm_models` warms.
_BUILD_ARTIFACT = {
    "build_profile": stages.EXEMPLARS_PROFILE,
    "build_kg": stages.KNOWLEDGE_GRAPH,
    "build_bank": stages.EXEMPLARS_BANK,
}

# The components, by the `config` name that holds each model. Written out rather than
# introspected because what a handler calls is not derivable from anything: `index`, `tag`,
# `generate` and `evaluate` all raise a `PipelineContext`, and building one writes whatever
# concept descriptions are missing — which is a model call the handler never mentions.
_COMPONENT_MODELS: dict[str, tuple[str, ...]] = {
    "transcribe": ("TRANSCRIBE_MODEL", "TRANSCRIBE_SEAM_MODEL"),
    "describe_concepts": ("DESCRIPTION_GENERATION_LLM", "REPAIR_LLM"),
    "index": ("DESCRIPTION_GENERATION_LLM", "REPAIR_LLM"),
    "tag": ("CONCEPT_TAGGER_LLM", "DESCRIPTION_GENERATION_LLM", "REPAIR_LLM"),
    "review_taggability": ("KG_TAGGABLE_MODEL", "REPAIR_LLM"),
    "generate": (
        "VARIANT_GENERATION_LLM",
        "ADMISSIBILITY_LLM",
        "CONCEPT_TAGGER_LLM",
        "DESCRIPTION_GENERATION_LLM",
        "REPAIR_LLM",
    ),
    # The three arms together: the naive and rag baselines generate and repair, and the
    # system arm is the whole generator, admissibility judge included.
    "evaluate": (
        "VARIANT_GENERATION_LLM",
        "ADMISSIBILITY_LLM",
        "CONCEPT_TAGGER_LLM",
        "DESCRIPTION_GENERATION_LLM",
        "REPAIR_LLM",
    ),
}


def _excluded() -> set[str]:
    return {config.EMBEDDING_LLM, config.GUARDRAIL_LLM}


def models_for(kind: str, params: dict | None = None) -> list[str]:
    """The generative models a job of this kind will call, in declaration order."""
    if kind in _BUILD_ARTIFACT:
        models = stages.build_models(_BUILD_ARTIFACT[kind])
    elif kind == "warm_models":
        # Warming is the GPU being written to, which is the local lane by definition even
        # when the model it warms would answer from somewhere else.
        models = inference.runtime_models()
    else:
        models = [getattr(config, name, None) for name in _COMPONENT_MODELS.get(kind, ())]

    excluded = _excluded()
    return [m for m in dict.fromkeys(models) if m and m not in excluded]


# Asking the engine rather than comparing `config.INFERENCE_ENGINE` against a literal: the
# plain Ollama engine answers with nothing remote, so one reading covers both. An engine
# that cannot even be built serves nothing remotely either.
def _remote_models() -> frozenset[str]:
    try:
        return inference.remote_models()
    except inference.InferenceError:
        return frozenset()


def backend_of(model: str) -> str:
    return REMOTE if model in _remote_models() else LOCAL


def backends_for(kind: str, params: dict | None = None) -> frozenset[str]:
    """The lanes a job of this kind has to hold at once in order to run.

    Empty means it calls no generative model, and a job that reserves nothing never waits
    for anything.

    This runs on the submit path, so it fails CLOSED rather than raising: a builder whose
    model list cannot be read is a reason to reserve everything and go back to one job at
    a time, never a reason to turn `POST /api/jobs` into a 500.
    """
    try:
        models = models_for(kind, params)
    except Exception as exc:  # noqa: BLE001 - degrade to one lane, never refuse the job
        logger.warning(
            f"[carriles] No se pudo decidir qué motores usa «{kind}» ({exc}); "
            "se reservan todos y el trabajo espera a que no haya nada más"
        )
        return frozenset(BACKENDS)

    remote = _remote_models()
    return frozenset(REMOTE if model in remote else LOCAL for model in models)
