"""Which backend each job kind competes for, so two of them can run at once.

Two scarce things sit behind this queue and they are not the same one: Ollama serves from a
single GPU, Cerebras over the network under a rolling quota. A local job and a remote one
contend for nothing at all.

A lane is reserved by the GENERATIVE models a job kind calls. The embedder and the guardrail
are deliberately outside the count — both small, both on Ollama whatever the engine is, and
all three co-resident — so a job whose generative work is remote reserves only `REMOTE` even
though it embeds locally throughout.

Everything is read through `config.<NAME>` at the moment a job is queued and never cached
here: the engine is switched from the panel while the process runs.
"""

from loguru import logger

from variatio import config, stages
from variatio.core import inference

LOCAL = "local"
REMOTE = "remote"

BACKENDS = (LOCAL, REMOTE)

# One, and not a setting: the GPU is one, and two jobs on it would do nothing but swap
# weights. The remote lane holds more than one because what is scarce there is a quota, not
# a machine, and `core/cerebras_budget.py` already books it call by call.
LOCAL_CAPACITY = 1


def capacity(backend: str) -> int:
    """Return how many jobs may hold this lane at once. Read live: the panel changes it hot."""
    if backend != REMOTE:
        return LOCAL_CAPACITY
    try:
        return max(1, int(config.CEREBRAS_MAX_CONCURRENT_JOBS))
    except (AttributeError, TypeError, ValueError):
        return 1


def capacities() -> dict[str, int]:
    """Return the room every lane has right now, for one pass of the dispatcher."""
    return {backend: capacity(backend) for backend in BACKENDS}

# `stages.build_models` is the builder's own declaration, so the phases and the lane cannot
# drift apart.
_BUILD_ARTIFACT = {
    "build_profile": stages.EXEMPLARS_PROFILE,
    "build_kg": stages.KNOWLEDGE_GRAPH,
    "build_bank": stages.EXEMPLARS_BANK,
}

# The components, by the `config` name holding each model. Written out rather than
# introspected: what a handler calls is not derivable from anything, since `index`, `tag`,
# `generate` and `evaluate` all raise a `PipelineContext`, and building one writes whatever
# concept descriptions are missing — a model call the handler never mentions.
_COMPONENT_MODELS: dict[str, tuple[str, ...]] = {
    "transcribe": ("TRANSCRIBE_MODEL", "TRANSCRIBE_SEAM_MODEL"),
    "describe_concepts": ("DESCRIPTION_GENERATION_LLM", "REPAIR_LLM"),
    "index": ("DESCRIPTION_GENERATION_LLM", "REPAIR_LLM"),
    "tag": ("CONCEPT_TAGGER_LLM", "DESCRIPTION_GENERATION_LLM", "REPAIR_LLM"),
    "review_taggability": ("KG_TAGGABLE_MODEL", "REPAIR_LLM"),
    # The writer is deliberately absent: a generate job runs the model its COMMISSION
    # chose, which `models_for` puts at the head of this list. Naming the installation's
    # default here as well would reserve its lane too, and with one offered model served
    # remotely and another on the GPU that is a lane the job never touches.
    "generate": (
        "ADMISSIBILITY_LLM",
        "CONCEPT_TAGGER_LLM",
        "DESCRIPTION_GENERATION_LLM",
        "REPAIR_LLM",
    ),
    # The three arms together: the two baselines generate and repair, and the system arm is
    # the whole generator, admissibility judge included. The writer of the two local arms
    # is absent for the generate kind's reason: since 2026-09-04 it is the evaluation's own
    # setting (`evaluation.local_model`), which `models_for` puts at the head of this list.
    "evaluate": (
        "ADMISSIBILITY_LLM",
        "CONCEPT_TAGGER_LLM",
        "DESCRIPTION_GENERATION_LLM",
        "REPAIR_LLM",
    ),
}


def _excluded() -> set[str]:
    """Return the two models that reserve nothing: small, always local, and co-resident."""
    return {config.EMBEDDING_LLM, config.GUARDRAIL_LLM}


def models_for(kind: str, params: dict | None = None) -> list[str]:
    """Return the generative models a job of this kind will call, in declaration order."""
    if kind in _BUILD_ARTIFACT:
        models = stages.build_models(_BUILD_ARTIFACT[kind])
    else:
        models = [getattr(config, name, None) for name in _COMPONENT_MODELS.get(kind, ())]

    if kind == "generate":
        models = [_writer(params), *models]
    elif kind == "evaluate":
        models = [_evaluation_writer(), *models]

    excluded = _excluded()
    return [m for m in dict.fromkeys(models) if m and m not in excluded]


def _writer(params: dict | None) -> str:
    """Return the model a generate commission will be written with.

    An unoffered name is not this module's error to raise — the submit route already
    refused it, and a lane calculation that raises turns a queueing problem into a 500.
    The default is what the job would fall back to anyway.
    """
    requested = (params or {}).get("model")
    try:
        return stages.resolve_generation_model(requested if isinstance(requested, str) else None)
    except stages.UnofferedModelError:
        return config.VARIANT_GENERATION_LLM


def _evaluation_writer() -> str:
    """Return the model an evaluation's two local proposals are written with.

    The evaluation's own setting, read through `evaluation.config` at dispatch time like everything
    else here — the panel edits it hot. Imported inside the function: the evaluation is mounted
    from `server/app.py` and nothing else under `server/` names it at module scope.
    """
    from evaluation import config as evaluation_config

    return evaluation_config.LOCAL_MODEL


def _remote_models() -> frozenset[str]:
    """Return the models served remotely, and nothing at all if the engine will not build.

    Asked of the engine rather than compared against `config.INFERENCE_ENGINE`: plain Ollama
    answers with nothing remote, so one reading covers both engines.
    """
    try:
        return inference.remote_models()
    except inference.InferenceError:
        return frozenset()


def backend_of(model: str) -> str:
    """Return the lane one model is served from."""
    return REMOTE if model in _remote_models() else LOCAL


def backends_for(kind: str, params: dict | None = None) -> frozenset[str]:
    """Return the lanes a job of this kind has to hold at once in order to run.

    Empty means it calls no generative model, and a job that reserves nothing never waits.

    This runs on the submit path, so it fails CLOSED rather than raising: a builder whose
    model list cannot be read is a reason to reserve everything and go back to one job at a
    time, never a reason to turn `POST /api/jobs` into a 500.
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
