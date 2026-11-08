"""The engine boundary: every model call this system makes goes through here.

No business logic ever reaches an SDK directly. The engines are their own packages:
`ollama/` (the local one) and `cerebras_ollama/` (the hybrid one, which keeps an Ollama engine
for what it does not serve); `interface.py` is what both implement.

THIS MODULE HOLDS NO ENGINE. The owner of a process builds an `engines.EngineSet` and fixes
the engine of each piece of work with `using(engine)`, a context variable: per thread, like
`progress` and `usage`. Every function below asks the engine of the current context, and
raises when there is none — the library never picks an engine on its own. A thread started
by the work (a pool) takes the context along with `contextvars.copy_context()`.

The types live in `types.py` and the `<think>` split in `thinking.py`; this module
re-exports both.
"""

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager

from loguru import logger

from .. import config, settings
from ..utils import progress
from .thinking import ThinkingSplitter, split_thinking
from .interface import Engine
from .types import GenerationResponse, InferenceError, ProgressSink, Sampling, TokenSink

_current: contextvars.ContextVar[Engine | None] = contextvars.ContextVar(
    "inference_engine", default=None
)


@contextmanager
def using(engine: Engine) -> Iterator[Engine]:
    """Fix `engine` as the one every call of this context makes, for the block.

    It fixes the engine's settings profile too (`settings.engine_profile()`): which model a
    phase calls, and how, is the engine's.
    """
    token = _current.set(engine)
    try:
        with settings.use_profile(engine.name):
            yield engine
    finally:
        _current.reset(token)


def generate(
    model: str,
    prompt: str,
    think: bool | str | None = None,
    system: str | None = None,
    images: list[str] | None = None,
    sampling: Sampling | None = None,
    format: dict | str | None = None,
    max_output_tokens: int | None = None,
    stop_on_loop: bool = False,
) -> GenerationResponse:
    """Ask the configured engine for one answer.

    `max_output_tokens` caps what the model may write and is the caller's to set — a
    transcription has a measured ceiling, a curation call does not — and the answer says
    through `truncated` whether the cap was hit. `stop_on_loop` is the caller's too: it
    asks the engine to stop reading an answer whose tail has become a repetition and to
    say so through `loop`. A transcription asks for it; a call under a grammar must not,
    since a list of forty identical objects is a shape the grammar allows.
    """
    return engine().generate(
        model=model,
        prompt=prompt,
        think=think,
        system=system,
        images=images,
        sampling=sampling,
        format=format,
        max_output_tokens=max_output_tokens,
        stop_on_loop=stop_on_loop,
    )


def generate_stream(
    model: str,
    prompt: str,
    think: bool | str | None = None,
    on_token: TokenSink | None = None,
    sampling: Sampling | None = None,
) -> GenerationResponse:
    """Ask the configured engine for one answer, token by token.

    The sink may gather tokens before it sends them (`progress.TokenBatch`); whatever it
    still holds is sent when the answer ends, cut short or not.
    """
    try:
        return engine().generate_stream(
            model=model,
            prompt=prompt,
            think=think,
            on_token=on_token,
            sampling=sampling,
        )
    finally:
        flush = getattr(on_token, "flush", None)
        if flush is not None:
            flush()


def embed(model: str, text: str) -> list[float]:
    """Embed one text. The single-text signature is part of the contract."""
    return engine().embed(model=model, text=text)


def embed_batch(model: str, texts: list[str]) -> list[list[float]]:
    """Embed several texts in one call."""
    return engine().embed_batch(model=model, texts=texts)


def sampling(phase: str, think: bool | str = False) -> Sampling:
    """Return how `phase` samples this call, given whether it reasons this time.

    What the phase leaves empty is decided here, at the last moment: the temperature by the
    judging pair — `TEMPERATURE_REASONING` when the call reasons, `TEMPERATURE_DETERMINISTIC`
    when it does not, which is what every call did before it had its own — and top-k and
    top-p by the model, by not being sent. An undeclared phase raises: a misspelt name would
    otherwise sample at the inherited values in silence.
    """
    own = config.SAMPLING[phase]
    temperature = own.get("temperature")
    if temperature is None:
        temperature = (
            config.TEMPERATURE_REASONING if think else config.TEMPERATURE_DETERMINISTIC
        )
    return Sampling(float(temperature), own.get("top_k"), own.get("top_p"))


def supports_thinking(model: str) -> bool:
    """Whether `model` has a reasoning mode to ask for."""
    return engine().supports_thinking(model)


def supports_vision(model: str) -> bool:
    """Whether `model` can read an image."""
    return engine().supports_vision(model)


def engine() -> Engine:
    """The engine fixed for the current context; raises when there is none."""
    current = _current.get()
    if current is None:
        raise InferenceError(
            "No hay motor de inferencia activo: el proceso no fijó ninguno para este trabajo"
        )
    return current


def engine_name() -> str:
    """The `engine.name` value of the engine fixed for the current context."""
    return engine().name


def is_available() -> bool:
    """Whether the engine answers at all."""
    return engine().is_available()


def require_engine() -> None:
    """Raise unless the engine of the current context answers.

    Every entry point that talks to a model calls this before its first phase; the entry points
    never do. On the hybrid engine it is the LOCAL half that is checked, which is what this
    process cannot do without — a Cerebras outage surfaces on its first remote call.
    """
    if not is_available():
        msg = f"Cannot connect to inference engine '{engine_name()}'. Make sure it is running before initializing the agent."
        logger.critical(msg)
        raise RuntimeError(msg)


def installed_models() -> list[str]:
    """The names of the models this engine can serve."""
    return engine().installed_models()


def installed_models_detail() -> list[dict]:
    """The models this engine can serve, with their sizes and where they are served."""
    return engine().installed_models_detail()


def running_models() -> list[dict]:
    """What is resident on the GPU right now."""
    return engine().running_models()


def remote_models() -> frozenset[str]:
    """Which of the engine's models are served remotely; empty on a purely local one.

    It is what lets a screen say "remoto" instead of pretending a hosted model sits on the
    disk.
    """
    return engine().remote_models()


def unload(model: str, is_embedding: bool = False) -> bool:
    """Free `model` from the GPU."""
    return engine().unload(model, is_embedding=is_embedding)


def unload_all() -> list[str]:
    """Free every resident model, returning the ones that went."""
    return engine().unload_all()


def pull_model(model: str, on_progress: ProgressSink | None = None) -> None:
    """Download `model` to the engine's disk."""
    engine().pull(model, on_progress)


def delete_model(model: str) -> None:
    """Remove `model` from the engine's disk."""
    engine().delete(model)


def required_models() -> dict[str, str]:
    """The models the registry asks for, keyed by the setting that asks for them.

    The offered generation models are numbered rather than named: they are one setting
    holding a list, and the key is what the delete guard prints when it refuses to remove
    a model from the disk. The first of them is `VARIANT_GENERATION_LLM` as well.
    """
    from ..settings import values
    from ..settings.derived import PHASES
    from ..settings.registry import EXTRA_MODEL_KEYS

    names = ["GUARDRAIL_LLM", "EMBEDDING_LLM", *PHASES.values()]
    required = {name: getattr(config, name) for name in names}
    for index, model in enumerate(config.GENERATION_MODELS):
        required[f"GENERATION_MODELS[{index}]"] = str(model)
    resolved = values()
    for key in EXTRA_MODEL_KEYS:
        if resolved.get(key):
            required[key] = str(resolved[key])
    return required


def ensure_models(models: list[str], label: str) -> None:
    """Check `models` are installed and pull what is missing; raise if one cannot be.

    It loads NOTHING into memory. The weights arrive with the first real call either way,
    and on an engine whose phases name different models a warm-up pays for a load the next
    phase evicts. What this buys is the fail-fast: a build that would die forty minutes in
    for want of a model dies here, before its first phase.

    `label` is interpolated into an English sentence, so it is an English noun phrase — the
    three builders used to pass a Spanish genitive and the log read "Checking the del perfil
    de ejemplares models", which is neither language.
    """
    unique = list(dict.fromkeys(models))
    logger.info(f"Checking the {label} models: {', '.join(unique)}")

    failed = []
    for m in unique:
        progress.checkpoint()
        if not ensure_model(m):
            failed.append(m)
    if failed:
        raise RuntimeError(f"No se pudieron instalar los modelos: {', '.join(failed)}")

    logger.success(f"{label} models available")


def ensure_model(model: str) -> bool:
    """Make sure `model` is installed, pulling it if it is not."""
    return engine().ensure_model(model)
