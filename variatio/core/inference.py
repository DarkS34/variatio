"""The engine boundary: every model call this system makes goes through here.

`config.INFERENCE_ENGINE` picks the implementation, and no business logic ever reaches an
SDK directly. The engines are their own modules: `ollama.py` (the local one) and
`cerebras.py` (the hybrid one, which keeps an Ollama engine for what it does not serve).
Both import this module's types, so it reaches them lazily, from `_engine_class`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger

from .. import config
from . import progress

TokenSink = Callable[[str, str], None]
ProgressSink = Callable[[int, int], None]

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"
_MAX_TAG = max(len(THINK_OPEN), len(THINK_CLOSE))


class InferenceError(Exception):
    """Anything the engine could not do, phrased for the panel rather than for a log."""


@dataclass
class GenerationResponse:
    """One answer, with the model's deliberation kept out of it.

    `truncated` says the engine stopped for want of output budget rather than because the
    model finished — Ollama's `done_reason == "length"`, Cerebras' `finish_reason ==
    "length"`. It is the engine's own reading and not a heuristic, which is what lets a
    caller treat a cut answer as a failure instead of as a short one.

    `loop` is the unit the answer was repeating when the engine stopped reading it — set
    only for a caller that asked with `stop_on_loop`, and the reason `response` ends where
    it does: what the model wrote up to the loop is there, the repetitions are not.
    """

    response: str
    thinking: str | None = None
    truncated: bool = False
    loop: str | None = None


@dataclass(frozen=True)
class Sampling:
    """How the engine draws each token: a temperature, and a top-k and top-p when set.

    An empty top-k or top-p is not sent, and the model's own value decides — its Modelfile
    on Ollama, the provider's default on Cerebras.
    """

    temperature: float
    top_k: int | None = None
    top_p: float | None = None


def split_thinking(
    text: str, sdk_thinking: str | None = None, truncated: bool = False, loop: str | None = None
) -> GenerationResponse:
    """Same split as the streaming path, for a response that arrived in one piece."""
    splitter = ThinkingSplitter()
    answer: list[str] = []
    thinking: list[str] = [sdk_thinking.strip()] if (sdk_thinking or "").strip() else []
    for part, channel in [*splitter.feed(text or ""), *splitter.flush()]:
        (thinking if channel == "thinking" else answer).append(part)
    return GenerationResponse(
        response="".join(answer).strip(),
        thinking="\n\n".join(p.strip() for p in thinking if p.strip()) or None,
        truncated=truncated,
        loop=loop,
    )



class ThinkingSplitter:
    """Routes `<think>…</think>` out of the answer, chunk by chunk.

    Some models report their reasoning in the SDK's own `thinking` field; others just
    print the tags inline in the response. Without this the inline ones flood the answer
    pane with their scratchpad and the final parse has to guess which of the JSON blobs
    they wrote along the way was the actual answer.

    Chunks arrive at arbitrary boundaries, so a tag can be cut in half between two of
    them: whatever trailing text could still grow into a tag is held back until the next
    chunk decides it.
    """

    def __init__(self) -> None:
        """Start outside a think block, holding nothing back."""
        self._inside = False
        self._pending = ""

    @property
    def inside(self) -> bool:
        """True when the stream ended (or paused) in the middle of a think block."""
        return self._inside

    def feed(self, text: str) -> list[tuple[str, str]]:
        """`(text, channel)` pairs for one chunk, with the tags themselves removed."""
        if not text:
            return []

        out: list[tuple[str, str]] = []
        buffer = self._pending + text
        self._pending = ""

        while buffer:
            tag = THINK_CLOSE if self._inside else THINK_OPEN
            index = buffer.lower().find(tag)
            if index < 0:
                break
            if index:
                out.append((buffer[:index], self._channel))
            buffer = buffer[index + len(tag) :]
            self._inside = not self._inside

        held = _partial_tag_length(buffer)
        if held:
            self._pending = buffer[len(buffer) - held :]
            buffer = buffer[: len(buffer) - held]
        if buffer:
            out.append((buffer, self._channel))
        return out

    @property
    def _channel(self) -> str:
        """Which channel the text being emitted right now belongs to."""
        return "thinking" if self._inside else "answer"

    def flush(self) -> list[tuple[str, str]]:
        """Whatever was held back waiting for a tag that never arrived."""
        if not self._pending:
            return []
        out = [(self._pending, self._channel)]
        self._pending = ""
        return out


def _partial_tag_length(buffer: str) -> int:
    """Length of the trailing slice that could still turn out to be a think tag."""
    lowered = buffer.lower()
    for size in range(min(len(buffer), _MAX_TAG - 1), 0, -1):
        suffix = lowered[-size:]
        if THINK_OPEN.startswith(suffix) or THINK_CLOSE.startswith(suffix):
            return size
    return 0


_ENGINE_NAMES = ("ollama", "cerebras+ollama")

_engine = None


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
        temperature = config.TEMPERATURE_REASONING if think else config.TEMPERATURE_DETERMINISTIC
    return Sampling(float(temperature), own.get("top_k"), own.get("top_p"))


def supports_thinking(model: str) -> bool:
    """Whether `model` has a reasoning mode to ask for."""
    return engine().supports_thinking(model)


def supports_vision(model: str) -> bool:
    """Whether `model` can read an image."""
    return engine().supports_vision(model)


def engine():
    """The configured engine, built once and kept until something invalidates it."""
    global _engine
    if _engine is None:
        cls = _engine_class(config.INFERENCE_ENGINE)
        if cls is None:
            raise InferenceError(
                f"Unknown inference engine '{config.INFERENCE_ENGINE}'. "
                f"Available: {', '.join(_ENGINE_NAMES)}"
            )
        _engine = cls()
    return _engine


def _engine_class(name: str):
    """Return the engine class called `name`, or None when nothing answers to it.

    Both engines live in their own modules and import this one, so they are reached here
    lazily rather than at import time.
    """
    from .ollama import OllamaEngine

    if name == OllamaEngine.name:
        return OllamaEngine
    if name == "cerebras+ollama":
        from .cerebras import HybridEngine

        return HybridEngine
    return None


def engine_name() -> str:
    """Which engine the configuration currently names."""
    return config.INFERENCE_ENGINE


def reset_engine() -> None:
    """Drop the cached engine.

    It holds the host it was built with, so a change to `INFERENCE_ENGINE` or
    `OLLAMA_HOST` is only real once this has run.
    """
    global _engine
    _engine = None


def is_available() -> bool:
    """Whether the engine answers at all."""
    return engine().is_available()


def require_engine() -> None:
    """Raise unless the configured inference engine answers.

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
    remote = getattr(engine(), "remote_models", None)
    return remote() if callable(remote) else frozenset()


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
