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

# `/api/tags` was asked for three times per `ensure_models` and once per health poll — every
# 15 s, per open tab — and all of it goes over the SSH tunnel to the GPU box. The listing only
# changes when something is pulled or deleted: this process invalidates on both, and the TTL
# is what still notices an `ollama pull` someone ran by hand on the box itself. Deliberately
# not a setting: residency (`/api/ps`) is the live measurement and is never cached.
_INSTALLED_TTL_SECONDS = 30.0


class InferenceError(Exception):
    pass


@dataclass
class GenerationResponse:
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


class OllamaEngine:
    name = "ollama"

    def __init__(self):
        self._client = ollama.Client(host=config.OLLAMA_HOST)
        self._capabilities: dict[str, list[str]] = {}
        self._installed: tuple[float, list[dict]] | None = None

    def is_available(self) -> bool:
        # Every failure is the same answer, "no", and the caller is a health check: catching
        # only `ConnectError` let a `ReadTimeout` — what a busy or tunnelled engine returns —
        # escape and turn `GET /api/health` into a 500 for the whole panel.
        try:
            response = httpx.get(config.OLLAMA_HOST, timeout=3.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    # Asking a model that has no reasoning mode to think is a hard error in Ollama, so
    # the request is only made of models that advertise the capability.
    #
    # THIS IS WHERE `True` BECOMES AN EFFORT LEVEL. The study's `Commission`, the
    # `generations.think` column and the UI switch still pass a boolean; a pipeline phase
    # passes what `settings.derived` resolved for it — `False`, or its own per-phase level
    # as a string, which travels through unchanged. `True` becomes the fixed
    # `DEFAULT_THINK_EFFORT` (the global THINK_EFFORT setting was removed 2026-08-24, per-
    # phase efforts replaced it; "low" stays the measured cap for the boolean callers).
    # `False` stays `False`, which is a different thing entirely (no reasoning at all) and
    # is what the constrained-decoding call sites depend on.
    #
    # A model whose renderer does not implement levels silently ignores the string and
    # reasons as it always did, so this is safe to send at any model that thinks: measured,
    # `qwen3.6:35b-a3b-q8_0` returns a byte-identical answer for `true`, `low` and `high`.
    def _think_option(self, model: str, think: bool | str | None) -> dict:
        if think is None:
            return {}
        if not self.supports_thinking(model):
            logger.debug(f"'{model}' no tiene modo de razonamiento; se ignora think={think}")
            return {}
        return {"think": DEFAULT_THINK_EFFORT if think is True else think}

    # Constrained decoding: `"json"` guarantees the syntax, a JSON Schema guarantees the
    # keys and their types. It is NOT compatible with reasoning on this stack — measured on
    # Ollama 0.32.13 + qwen3.8:27b: the grammar applies from the first token, so the model
    # can never emit the `</think>` that closes the reasoning channel, Ollama attributes the
    # whole (perfectly valid) JSON to `thinking` and `response` comes back EMPTY. It also
    # means there is no deliberation left to attribute — the answer starts at `{`. So a call
    # site either thinks or constrains, never both.
    @staticmethod
    def _format_option(format: dict | str | None) -> dict:
        return {} if format is None else {"format": format}

    # Left to itself Ollama allocates the KV cache for the model's declared context,
    # which is where most of this box's VRAM was going. `config.LLM_CONTEXT` is the
    # single place that decides it, so no call site has to know.
    #
    # `temperature` shares the same options dict, so both are built here: assembling them
    # separately is how one of them ends up overwriting the other.
    #
    # It is resolved rather than merely forwarded: a generative call that names none gets
    # `config.TEMPERATURE_DEFAULT` and never the engine's own 0.8, so the worst a forgotten
    # argument can do is make a call deterministic. Only the two generative paths resolve it
    # — `embed`/`embed_batch` call this with nothing and must keep sending no temperature at
    # all, since an embedding has no sampler to steer.
    @staticmethod
    def _context_option(model: str, temperature: float | None = None) -> dict:
        options: dict = {}
        num_ctx = config.LLM_CONTEXT.get(model)
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        if temperature is not None:
            options["temperature"] = temperature
        return {"options": options} if options else {}

    @staticmethod
    def _temperature(temperature: float | None) -> float:
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
        system_option = {} if system is None else {"system": system}
        # Base64 PNGs, as Ollama expects them. Refusing up front beats the empty answer a
        # text-only model gives when it is handed a picture it cannot see.
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
            raise InferenceError(f"Ollama generation failed for model '{model}': {e}") from e
        return split_thinking(resp.response, getattr(resp, "thinking", None))

    def generate_stream(
        self,
        model: str,
        prompt: str,
        think: bool | str | None = None,
        on_token: TokenSink | None = None,
        temperature: float | None = None,
    ) -> GenerationResponse:
        if on_token is None:
            return self.generate(
                model=model, prompt=prompt, think=think, temperature=temperature
            )

        splitter = ThinkingSplitter()
        answer: list[str] = []
        thinking: list[str] = []

        def take(parts: list[tuple[str, str]]) -> None:
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
                # The response text may carry inline `<think>` spans; the answer channel
                # must only ever receive what is actually part of the answer.
                take(splitter.feed(chunk.response or ""))
                # Streaming hands back control on every chunk, which is exactly where a
                # cooperative cancel can take effect without waiting for the full answer.
                progress.checkpoint()
            take(splitter.flush())
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama generation failed for model '{model}': {e}") from e

        return GenerationResponse(
            response="".join(answer).strip(), thinking="".join(thinking).strip() or None
        )

    def capabilities(self, model: str) -> list[str]:
        if model not in self._capabilities:
            try:
                capabilities = list(self._client.show(model).capabilities or [])
            except (ollama.ResponseError, httpx.RequestError) as e:
                logger.warning(f"No se pudieron leer las capacidades de '{model}': {e}")
                capabilities = []
            self._capabilities[model] = capabilities
        return self._capabilities[model]

    def supports_thinking(self, model: str) -> bool:
        return "thinking" in self.capabilities(model)

    def supports_vision(self, model: str) -> bool:
        return "vision" in self.capabilities(model)

    def embed(self, model: str, text: str) -> list[float]:
        try:
            return self._client.embeddings(
                model=model, prompt=text, **self._context_option(model)
            )["embedding"]
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama embedding failed for model '{model}': {e}") from e

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return list(self._client.embed(model=model, input=texts, **self._context_option(model))["embeddings"])
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama batch embedding failed for model '{model}': {e}") from e

    def installed_models(self) -> list[str]:
        return [info["model"] for info in self.installed_models_detail()]

    def installed_models_detail(self) -> list[dict]:
        cached = self._installed
        if cached is not None and time.monotonic() - cached[0] < _INSTALLED_TTL_SECONDS:
            return cached[1]
        try:
            listing = self._client.list()["models"]
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Could not list Ollama models: {e}") from e
        detail = [
            {"model": info["model"], "size": int(info["size"]) if info.get("size") else None}
            for info in listing
        ]
        self._installed = (time.monotonic(), detail)
        return detail

    # What is loaded NOW, which is the only thing that can actually be measured from here: the
    # session does not run on the GPU machine, so `nvidia-smi` answers about another card and
    # `/api/ps` is the only honest reading of residency and VRAM. `expires_at` says until
    # when, so an eviction can be told from the timer running out.
    def running_models(self) -> list[dict]:
        try:
            response = self._client.ps()
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Could not read the resident Ollama models: {e}") from e
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

    # `ollama stop <model>`, which underneath is not an endpoint of its own: it is an ordinary
    # call with `keep_alive=0`, and the server unloads the weights when it finishes. It is sent
    # through the endpoint that matches the model — an embedder cannot generate and would
    # answer 400 — and with an empty prompt, which is what `warmup` does.
    def unload(self, model: str, is_embedding: bool = False) -> bool:
        try:
            if is_embedding:
                self._client.embed(model=model, input="", keep_alive=0)
            else:
                self._client.generate(model=model, prompt="", keep_alive=0)
            return True
        except (ollama.ResponseError, httpx.RequestError) as e:
            logger.warning(f"No se pudo descargar '{model}' de la GPU: {e}")
            return False

    def unload_all(self) -> list[str]:
        try:
            resident = [info["model"] for info in self.running_models() if info["model"]]
        except InferenceError as e:
            logger.warning(f"No se pudo leer qué modelos están cargados: {e}")
            return []
        return [
            model
            for model in resident
            if self.unload(model, is_embedding=self._looks_like_embedding(model))
        ]

    # `config.EMBEDDING_MODELS` names the ones this instance uses; `/api/ps` may also return
    # any other the server has loaded on its own, and for those the declared capability is the
    # only reliable source.
    def _looks_like_embedding(self, model: str) -> bool:
        if model in config.EMBEDDING_MODELS:
            return True
        return "embedding" in self.capabilities(model)

    def ensure_model(self, model: str) -> bool:
        if model in self.installed_models():
            return True
        return self._pull(model)

    def warmup(self, model: str, is_embedding: bool = False) -> None:
        if is_embedding:
            self.embed(model, "")
        else:
            self.generate(model, "")

    def _pull(self, model: str) -> bool:
        pbar = None

        def on_progress(completed: int, total: int) -> None:
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
        logger.info(f"Descargando el modelo '{model}'")
        try:
            for partial in self._client.pull(model, stream=True):
                total = int(partial.get("total") or 0)
                completed = int(partial.get("completed") or 0)
                if on_progress is not None:
                    on_progress(completed, total)
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Falló la descarga de '{model}': {e}") from e
        self._capabilities.pop(model, None)
        self._installed = None
        logger.success(f"Modelo '{model}' descargado")

    def delete(self, model: str) -> None:
        try:
            self._client.delete(model)
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"No se pudo borrar '{model}' del disco: {e}") from e
        self._capabilities.pop(model, None)
        self._installed = None
        logger.info(f"Modelo '{model}' borrado del disco del motor")


_ENGINE_NAMES = ("ollama", "cerebras+ollama")

_engine = None


# The hybrid engine lives in its own module and imports this one, so it is reached lazily
# here rather than at import time — same trick, other direction, as the registry's optional
# study import.
def _engine_class(name: str):
    if name == OllamaEngine.name:
        return OllamaEngine
    if name == "cerebras+ollama":
        from .cerebras import HybridEngine

        return HybridEngine
    return None


def engine():
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
    return config.INFERENCE_ENGINE


# The engine is built once and holds the host it was built with, so a change to
# `INFERENCE_ENGINE` or `OLLAMA_HOST` is only real once the cached one is dropped.
def reset_engine() -> None:
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
    return engine().generate_stream(
        model=model,
        prompt=prompt,
        think=think,
        on_token=on_token,
        temperature=temperature,
    )


def supports_thinking(model: str) -> bool:
    return engine().supports_thinking(model)


def judgement_temperature(think: bool | str) -> float:
    return config.TEMPERATURE_REASONING if think else config.TEMPERATURE_DETERMINISTIC


def supports_vision(model: str) -> bool:
    return engine().supports_vision(model)


def embed(model: str, text: str) -> list[float]:
    return engine().embed(model=model, text=text)


def embed_batch(model: str, texts: list[str]) -> list[list[float]]:
    return engine().embed_batch(model=model, texts=texts)


def is_available() -> bool:
    return engine().is_available()


def ensure_model(model: str) -> bool:
    return engine().ensure_model(model)


def installed_models() -> list[str]:
    return engine().installed_models()


def installed_models_detail() -> list[dict]:
    return engine().installed_models_detail()


def running_models() -> list[dict]:
    return engine().running_models()


# Which of the engine's models are served remotely — empty on a purely local engine. It is
# what lets a screen say «remoto» instead of pretending a hosted model sits on the disk.
def remote_models() -> frozenset[str]:
    remote = getattr(engine(), "remote_models", None)
    return remote() if callable(remote) else frozenset()


def unload(model: str, is_embedding: bool = False) -> bool:
    return engine().unload(model, is_embedding=is_embedding)


def unload_all() -> list[str]:
    return engine().unload_all()


def pull_model(model: str, on_progress: ProgressSink | None = None) -> None:
    engine().pull(model, on_progress)


def delete_model(model: str) -> None:
    engine().delete(model)


def required_models() -> dict[str, str]:
    """The models the registry asks for, keyed by the setting that asks for them."""
    from ..settings.derived import PHASES

    names = ["LLM_MAIN", "GUARDRAIL_LLM", "EMBEDDING_LLM", *PHASES.values()]
    return {name: getattr(config, name) for name in names}


def runtime_models() -> list[str]:
    names = [
        "LLM_MAIN",
        "GUARDRAIL_LLM",
        "EMBEDDING_LLM",
        "DESCRIPTION_GENERATION_LLM",
        "CONCEPT_TAGGER_LLM",
        "VARIANT_GENERATION_LLM",
        "ADMISSIBILITY_LLM",
        "REPAIR_LLM",
    ]
    return list(dict.fromkeys(getattr(config, name) for name in names))


def warmup(model: str, is_embedding: bool = False) -> None:
    engine().warmup(model, is_embedding=is_embedding)


def ensure_models(models: list[str], label: str) -> None:
    unique = list(dict.fromkeys(models))
    logger.info(f"Preparando los modelos {label}: {', '.join(unique)}")

    failed = [m for m in unique if not ensure_model(m)]
    if failed:
        raise RuntimeError(f"No se pudieron instalar los modelos: {', '.join(failed)}")

    for m in unique:
        progress.checkpoint()
        warmup(m, is_embedding=(m in config.EMBEDDING_MODELS))

    logger.success(f"Modelos {label} listos")
