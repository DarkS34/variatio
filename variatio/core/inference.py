"""The engine boundary: every model call this system makes goes through here.

`config.INFERENCE_ENGINE` picks the implementation, and no business logic ever reaches an
SDK directly.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import ollama
from loguru import logger
from tqdm import tqdm

from .. import config
from . import progress

TokenSink = Callable[[str, str], None]
ProgressSink = Callable[[int, int], None]

DEFAULT_THINK_EFFORT = "low"

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"
_MAX_TAG = max(len(THINK_OPEN), len(THINK_CLOSE))

# What is installed changes only on a pull or a delete, and this process invalidates on
# both: the TTL is only what notices an `ollama pull` run by hand on the GPU box. Residency
# (`/api/ps`) is the live measurement and is never cached.
_INSTALLED_TTL_SECONDS = 30.0


class InferenceError(Exception):
    """Anything the engine could not do, phrased for the panel rather than for a log."""


@dataclass
class GenerationResponse:
    """One answer, with the model's deliberation kept out of it."""

    response: str
    thinking: str | None = None


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

    def flush(self) -> list[tuple[str, str]]:
        """Whatever was held back waiting for a tag that never arrived."""
        if not self._pending:
            return []
        out = [(self._pending, self._channel)]
        self._pending = ""
        return out

    @property
    def _channel(self) -> str:
        """Which channel the text being emitted right now belongs to."""
        return "thinking" if self._inside else "answer"


def _partial_tag_length(buffer: str) -> int:
    """Length of the trailing slice that could still turn out to be a think tag."""
    lowered = buffer.lower()
    for size in range(min(len(buffer), _MAX_TAG - 1), 0, -1):
        suffix = lowered[-size:]
        if THINK_OPEN.startswith(suffix) or THINK_CLOSE.startswith(suffix):
            return size
    return 0


def split_thinking(text: str, sdk_thinking: str | None = None) -> GenerationResponse:
    """Same split as the streaming path, for a response that arrived in one piece."""
    splitter = ThinkingSplitter()
    answer: list[str] = []
    thinking: list[str] = [sdk_thinking.strip()] if (sdk_thinking or "").strip() else []
    for part, channel in [*splitter.feed(text or ""), *splitter.flush()]:
        (thinking if channel == "thinking" else answer).append(part)
    return GenerationResponse(
        response="".join(answer).strip(),
        thinking="\n\n".join(p.strip() for p in thinking if p.strip()) or None,
    )


def _upstream_error(action: str, e: Exception) -> str:
    """Phrase an engine failure for the panel: what failed, against which host, and how.

    The engine's own reply is not ours to hand back — `ollama.ResponseError` carries the
    raw upstream body and these messages travel to the panel — so the body goes to the log
    at debug and only the status leaves.
    """
    logger.debug(f"[ollama] {action}, against '{config.OLLAMA_HOST}': {e}")
    status = getattr(e, "status_code", None)
    if status:
        return f"{action}: el motor en '{config.OLLAMA_HOST}' respondió {status}"
    return (
        f"{action}: no se pudo hablar con el motor en '{config.OLLAMA_HOST}' "
        f"({type(e).__name__})"
    )


class OllamaEngine:
    """The local half: an Ollama server, reached over `config.OLLAMA_HOST`."""

    name = "ollama"

    def __init__(self):
        """Open the client and start the per-model capability and listing caches."""
        self._client = ollama.Client(host=config.OLLAMA_HOST)
        self._capabilities: dict[str, list[str]] = {}
        self._installed: tuple[float, list[dict]] | None = None

    def is_available(self) -> bool:
        """Whether the engine answers at all.

        Every failure is the same answer to a health check, `ReadTimeout` included:
        catching only `ConnectError` let what a busy or tunnelled engine returns escape and
        turn `GET /api/health` into a 500 for the whole panel.
        """
        try:
            response = httpx.get(config.OLLAMA_HOST, timeout=3.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _think_option(self, model: str, think: bool | str | None) -> dict:
        """Turn `think` into Ollama's own option, at the last hop before the call.

        THIS IS WHERE `True` BECOMES AN EFFORT LEVEL — with `cerebras.reasoning_effort`,
        the only place it does. The boolean callers (the study's `Commission`, the
        `generations.think` column, the UI switch) get the fixed `DEFAULT_THINK_EFFORT`; a
        pipeline phase passes what `settings.derived` resolved for it, so a string travels
        through untouched and `False` stays `False` — no reasoning at all, which the
        constrained-decoding call sites depend on.

        Asking a model with no reasoning mode to think is a hard error in Ollama, so the
        option is only sent to models advertising the capability. A model whose renderer
        ignores levels answers as it always did: measured, `qwen3.6:35b-a3b-q8_0` returns a
        byte-identical answer for `true`, `low` and `high`.
        """
        if think is None:
            return {}
        if not self.supports_thinking(model):
            logger.debug(f"'{model}' has no reasoning mode; ignoring think={think}")
            return {}
        return {"think": DEFAULT_THINK_EFFORT if think is True else think}

    @staticmethod
    def _format_option(format: dict | str | None) -> dict:
        """Constrain the decoding: `"json"` fixes the syntax, a schema the keys and types.

        A grammar is NOT compatible with reasoning on this stack — measured on Ollama
        0.32.13 + qwen3.8:27b, it applies from the first token, so the model can never emit
        the `</think>` that closes the reasoning channel, Ollama attributes the whole valid
        JSON to `thinking` and `response` comes back EMPTY. A call site either thinks or
        constrains, never both.
        """
        return {} if format is None else {"format": format}

    @staticmethod
    def _context_option(model: str, temperature: float | None = None) -> dict:
        """Build the per-call options: the KV cache cap and the sampler's temperature.

        Left to itself Ollama sizes the KV cache from the model's declared context, which
        is where most of this box's VRAM was going; `config.LLM_CONTEXT` decides it in one
        place so no call site has to know. Both options share one dict, so building them
        apart is how one ends up overwriting the other.

        Only the two generative paths resolve a temperature: `embed`/`embed_batch` call
        this with none and must keep sending none, an embedding having no sampler to steer.
        """
        options: dict = {}
        num_ctx = config.LLM_CONTEXT.get(model)
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        if temperature is not None:
            options["temperature"] = temperature
        return {"options": options} if options else {}

    @staticmethod
    def _temperature(temperature: float | None) -> float:
        """Resolve a generative call's temperature, never leaving the engine's own 0.8.

        The worst a forgotten argument can do is make a call deterministic.
        """
        return config.TEMPERATURE_DEFAULT if temperature is None else temperature

    def generate(
        self,
        model: str,
        prompt: str,
        think: bool | str | None = None,
        system: str | None = None,
        images: list[str] | None = None,
        temperature: float | None = None,
        format: dict | str | None = None,
    ) -> GenerationResponse:
        """Ask `model` for one answer, with the reasoning split out of it.

        Images are base64 PNGs. A text-only model handed a picture answers empty rather
        than failing, so it is refused up front instead.
        """
        system_option = {} if system is None else {"system": system}
        image_option: dict = {}
        if images:
            if not self.supports_vision(model):
                raise InferenceError(
                    f"Model '{model}' has no vision capability, so it cannot read the "
                    f"{len(images)} image(s) it was given"
                )
            image_option = {"images": list(images)}
        try:
            resp = self._client.generate(
                model=model,
                prompt=prompt,
                **system_option,
                **image_option,
                **self._think_option(model, think),
                **self._format_option(format),
                **self._context_option(model, self._temperature(temperature)),
            )
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(_upstream_error(f"Falló la generación con '{model}'", e)) from e
        return split_thinking(resp.response, getattr(resp, "thinking", None))

    def generate_stream(
        self,
        model: str,
        prompt: str,
        think: bool | str | None = None,
        on_token: TokenSink | None = None,
        temperature: float | None = None,
    ) -> GenerationResponse:
        """Stream one answer, feeding each token to `on_token` as it arrives.

        Falls back to the plain request when nobody is listening. The response text may
        carry inline `<think>` spans, so it goes through the splitter before reaching the
        answer channel, and every chunk is a point where a cancellation can take effect.
        """
        if on_token is None:
            return self.generate(
                model=model, prompt=prompt, think=think, temperature=temperature
            )

        splitter = ThinkingSplitter()
        answer: list[str] = []
        thinking: list[str] = []

        def take(parts: list[tuple[str, str]]) -> None:
            """Collect the splitter's output and forward it to the caller's sink."""
            for text, channel in parts:
                (thinking if channel == "thinking" else answer).append(text)
                on_token(text, channel)

        try:
            for chunk in self._client.generate(
                model=model,
                prompt=prompt,
                stream=True,
                **self._think_option(model, think),
                **self._context_option(model, self._temperature(temperature)),
            ):
                thought = getattr(chunk, "thinking", None)
                if thought:
                    thinking.append(thought)
                    on_token(thought, "thinking")
                take(splitter.feed(chunk.response or ""))
                progress.checkpoint()
            take(splitter.flush())
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(_upstream_error(f"Falló la generación con '{model}'", e)) from e

        return GenerationResponse(
            response="".join(answer).strip(), thinking="".join(thinking).strip() or None
        )

    def capabilities(self, model: str) -> list[str]:
        """What the model declares it can do, asked once per process and remembered."""
        if model not in self._capabilities:
            try:
                capabilities = list(self._client.show(model).capabilities or [])
            except (ollama.ResponseError, httpx.RequestError) as e:
                logger.warning(f"Could not read the capabilities of '{model}': {e}")
                capabilities = []
            self._capabilities[model] = capabilities
        return self._capabilities[model]

    def supports_thinking(self, model: str) -> bool:
        """Whether the model has a reasoning mode to ask for."""
        return "thinking" in self.capabilities(model)

    def supports_vision(self, model: str) -> bool:
        """Whether the model can read an image."""
        return "vision" in self.capabilities(model)

    def embed(self, model: str, text: str) -> list[float]:
        """Embed one text."""
        try:
            return self._client.embeddings(
                model=model, prompt=text, **self._context_option(model)
            )["embedding"]
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(_upstream_error(f"Falló el embedding con '{model}'", e)) from e

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        """Embed several texts in one call, in the order they were given."""
        if not texts:
            return []
        try:
            return list(self._client.embed(model=model, input=texts, **self._context_option(model))["embeddings"])
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(
                _upstream_error(f"Falló el embedding por lotes con '{model}'", e)
            ) from e

    def installed_models(self) -> list[str]:
        """The names of the models on the engine's disk."""
        return [info["model"] for info in self.installed_models_detail()]

    def installed_models_detail(self) -> list[dict]:
        """The models on the engine's disk with their sizes, cached for a few seconds."""
        cached = self._installed
        if cached is not None and time.monotonic() - cached[0] < _INSTALLED_TTL_SECONDS:
            return cached[1]
        try:
            listing = self._client.list()["models"]
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(
                _upstream_error("No se pudieron listar los modelos de Ollama", e)
            ) from e
        detail = [
            {"model": info["model"], "size": int(info["size"]) if info.get("size") else None}
            for info in listing
        ]
        self._installed = (time.monotonic(), detail)
        return detail

    def running_models(self) -> list[dict]:
        """What is resident on the GPU right now, with its VRAM and its expiry.

        The only honest reading available: this process does not run on the GPU machine, so
        `nvidia-smi` answers about another card. `expires_at` is what tells an eviction
        from the keep-alive timer simply running out.
        """
        try:
            response = self._client.ps()
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(
                _upstream_error("No se pudieron leer los modelos residentes", e)
            ) from e
        return [
            {
                "model": info.model or info.name or "",
                "size": int(info.size) if info.size else None,
                "size_vram": int(info.size_vram) if info.size_vram else None,
                "context_length": info.context_length,
                "expires_at": info.expires_at.isoformat() if info.expires_at else None,
            }
            for info in response.models
        ]

    def unload(self, model: str, is_embedding: bool = False) -> bool:
        """Free `model` from the GPU, as `ollama stop` does.

        There is no endpoint for it: an ordinary empty call with `keep_alive=0` makes the
        server unload the weights when it finishes. It has to go through the endpoint that
        matches the model — an embedder cannot generate and answers 400.
        """
        try:
            if is_embedding:
                self._client.embed(model=model, input="", keep_alive=0)
            else:
                self._client.generate(model=model, prompt="", keep_alive=0)
            return True
        except (ollama.ResponseError, httpx.RequestError) as e:
            logger.warning(f"Could not unload '{model}' from the GPU: {e}")
            return False

    def unload_all(self) -> list[str]:
        """Free every resident model, returning the ones that actually went."""
        try:
            resident = [info["model"] for info in self.running_models() if info["model"]]
        except InferenceError as e:
            logger.warning(f"Could not read which models are loaded: {e}")
            return []
        return [
            model
            for model in resident
            if self.unload(model, is_embedding=self._looks_like_embedding(model))
        ]

    def _looks_like_embedding(self, model: str) -> bool:
        """Whether `model` has to be unloaded through the embedding endpoint.

        `config.EMBEDDING_MODELS` names the ones this instance uses; `/api/ps` may also
        return one the server loaded on its own, and there the declared capability is the
        only reliable source.
        """
        if model in config.EMBEDDING_MODELS:
            return True
        return "embedding" in self.capabilities(model)

    def ensure_model(self, model: str) -> bool:
        """Make sure `model` is on disk, pulling it if it is not. Nothing is loaded."""
        if model in self.installed_models():
            return True
        return self._pull(model)

    def _pull(self, model: str) -> bool:
        """Download `model` with a terminal progress bar; returns whether it arrived."""
        pbar = None

        def on_progress(completed: int, total: int) -> None:
            """Open the bar on the first sized chunk and advance it thereafter."""
            nonlocal pbar
            if total <= 0:
                return
            if pbar is None:
                pbar = tqdm(total=total, unit="B", unit_scale=True, desc=model)
            pbar.update(completed - pbar.n)

        try:
            self.pull(model, on_progress)
        except InferenceError as e:
            logger.error(str(e))
            return False
        finally:
            if pbar is not None:
                pbar.close()
        return True

    def pull(self, model: str, on_progress: ProgressSink | None = None) -> None:
        """Download `model` to the engine's disk, invalidating both caches after it."""
        logger.info(f"Pulling model '{model}'")
        try:
            for partial in self._client.pull(model, stream=True):
                total = int(partial.get("total") or 0)
                completed = int(partial.get("completed") or 0)
                if on_progress is not None:
                    on_progress(completed, total)
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(_upstream_error(f"Falló la descarga de '{model}'", e)) from e
        self._capabilities.pop(model, None)
        self._installed = None
        logger.success(f"Model '{model}' pulled")

    def delete(self, model: str) -> None:
        """Remove `model` from the engine's disk, invalidating both caches after it."""
        try:
            self._client.delete(model)
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(
                _upstream_error(f"No se pudo borrar '{model}' del disco", e)
            ) from e
        self._capabilities.pop(model, None)
        self._installed = None
        logger.info(f"Model '{model}' deleted from the engine's disk")


_ENGINE_NAMES = ("ollama", "cerebras+ollama")

_engine = None


def _engine_class(name: str):
    """Return the engine class called `name`, or None when nothing answers to it.

    The hybrid engine lives in its own module and imports this one, so it is reached here
    lazily rather than at import time.
    """
    if name == OllamaEngine.name:
        return OllamaEngine
    if name == "cerebras+ollama":
        from .cerebras import HybridEngine

        return HybridEngine
    return None


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


def generate(
    model: str,
    prompt: str,
    think: bool | str | None = None,
    system: str | None = None,
    images: list[str] | None = None,
    temperature: float | None = None,
    format: dict | str | None = None,
) -> GenerationResponse:
    """Ask the configured engine for one answer."""
    return engine().generate(
        model=model,
        prompt=prompt,
        think=think,
        system=system,
        images=images,
        temperature=temperature,
        format=format,
    )


def generate_stream(
    model: str,
    prompt: str,
    think: bool | str | None = None,
    on_token: TokenSink | None = None,
    temperature: float | None = None,
) -> GenerationResponse:
    """Ask the configured engine for one answer, token by token."""
    return engine().generate_stream(
        model=model,
        prompt=prompt,
        think=think,
        on_token=on_token,
        temperature=temperature,
    )


def supports_thinking(model: str) -> bool:
    """Whether `model` has a reasoning mode to ask for."""
    return engine().supports_thinking(model)


def judgement_temperature(think: bool | str) -> float:
    """The temperature a judging phase calls at, paired with whether it reasons."""
    return config.TEMPERATURE_REASONING if think else config.TEMPERATURE_DETERMINISTIC


def supports_vision(model: str) -> bool:
    """Whether `model` can read an image."""
    return engine().supports_vision(model)


def embed(model: str, text: str) -> list[float]:
    """Embed one text. The single-text signature is part of the contract."""
    return engine().embed(model=model, text=text)


def embed_batch(model: str, texts: list[str]) -> list[list[float]]:
    """Embed several texts in one call."""
    return engine().embed_batch(model=model, texts=texts)


def is_available() -> bool:
    """Whether the engine answers at all."""
    return engine().is_available()


def ensure_model(model: str) -> bool:
    """Make sure `model` is installed, pulling it if it is not."""
    return engine().ensure_model(model)


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

    It is what lets a screen say «remoto» instead of pretending a hosted model sits on the
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
    """The models the registry asks for, keyed by the setting that asks for them."""
    from ..settings.derived import PHASES

    names = ["GUARDRAIL_LLM", "EMBEDDING_LLM", *PHASES.values()]
    return {name: getattr(config, name) for name in names}


def ensure_models(models: list[str], label: str) -> None:
    """Check `models` are installed and pull what is missing; raise if one cannot be.

    It loads NOTHING into memory. The weights arrive with the first real call either way,
    and on an engine whose phases name different models a warm-up pays for a load the next
    phase evicts. What this buys is the fail-fast: a build that would die forty minutes in
    for want of a model dies here, before its first phase.
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
