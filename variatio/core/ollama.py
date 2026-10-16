"""The local engine: Ollama, reached through its Python SDK and nowhere else.

`core/inference.py` is the boundary every model call goes through; this is the engine it
builds when `config.INFERENCE_ENGINE` is `ollama`, and the half of the hybrid engine
(`core/cerebras.py`) that stays local — the guardrail, the embedder and every model Cerebras
does not serve. The only module that imports the `ollama` SDK.
"""

import time

import httpx
import ollama
from loguru import logger
from tqdm import tqdm

from .. import config
from . import progress, repetition, usage
from .inference import (
    GenerationResponse,
    InferenceError,
    ProgressSink,
    Sampling,
    ThinkingSplitter,
    TokenSink,
    split_thinking,
)

# What is installed changes only on a pull or a delete, and this process invalidates on
# both: the TTL is only what notices an `ollama pull` run by hand on the GPU box. Residency
# (`/api/ps`) is the live measurement and is never cached.
_INSTALLED_TTL_SECONDS = 30.0


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

    def generate(
        self,
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
        """Ask `model` for one answer, with the reasoning split out of it.

        Images are base64 PNGs or JPEGs. A text-only model handed a picture answers empty
        rather than failing, so it is refused up front instead. With `stop_on_loop` the
        stream is abandoned the moment its tail is a repetition (`repetition.detect_tail`), so
        a model locked on a drawn grid stops costing tokens and time at once instead of
        at the output cap; the answer then carries the repeated unit as `loop`.

        THE ANSWER IS STREAMED EVEN THOUGH NOBODY IS WATCHING IT, and that is the whole
        difference between a stop that lands and one that does not. Cancellation is
        cooperative — a loop checks `progress.checkpoint()` between its units of work — so
        with the answer arriving in one blocking read the smallest unit is a whole model
        call, and on a contended box that is minutes.

        Streaming makes the unit a token. Nothing is emitted — this is not
        `generate_stream`, which exists to feed a live sink and is why a build must not use
        it — so no event travels and the reassembled answer is what the plain request would
        have returned, the transport being the only thing that changed. Abandoning the
        iterator closes the connection, and Ollama stops generating when its client goes
        away: the stop gives the GPU back instead of paying for an answer nobody will read.
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
            stream = self._client.generate(
                model=model,
                prompt=prompt,
                stream=True,
                **system_option,
                **image_option,
                **self._think_option(model, think),
                **self._format_option(format),
                **self._context_option(model, self._sampling(sampling), max_output_tokens),
            )
            answer, thinking, truncated, loop, counts = _drain(stream, stop_on_loop)
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(_upstream_error(f"Falló la generación con '{model}'", e)) from e
        usage.record(self.name, model, *counts)
        return split_thinking(answer, thinking or None, truncated, loop)

    def generate_stream(
        self,
        model: str,
        prompt: str,
        think: bool | str | None = None,
        on_token: TokenSink | None = None,
        sampling: Sampling | None = None,
    ) -> GenerationResponse:
        """Stream one answer, feeding each token to `on_token` as it arrives.

        Falls back to the plain request when nobody is listening. The response text may
        carry inline `<think>` spans, so it goes through the splitter before reaching the
        answer channel, and every chunk is a point where a cancellation can take effect.
        """
        if on_token is None:
            return self.generate(model=model, prompt=prompt, think=think, sampling=sampling)

        splitter = ThinkingSplitter()
        answer: list[str] = []
        thinking: list[str] = []

        def take(parts: list[tuple[str, str]]) -> None:
            """Collect the splitter's output and forward it to the caller's sink."""
            for text, channel in parts:
                (thinking if channel == "thinking" else answer).append(text)
                on_token(text, channel)

        counts: tuple[int | None, int | None] = (None, None)
        try:
            for chunk in self._client.generate(
                model=model,
                prompt=prompt,
                stream=True,
                **self._think_option(model, think),
                **self._context_option(model, self._sampling(sampling)),
            ):
                thought = getattr(chunk, "thinking", None)
                if thought:
                    thinking.append(thought)
                    on_token(thought, "thinking")
                take(splitter.feed(chunk.response or ""))
                counts = _counts(chunk, counts)
                progress.checkpoint()
            take(splitter.flush())
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(_upstream_error(f"Falló la generación con '{model}'", e)) from e
        finally:
            usage.record(self.name, model, *counts)

        return GenerationResponse(
            response="".join(answer).strip(), thinking="".join(thinking).strip() or None
        )

    def _think_option(self, model: str, think: bool | str | None) -> dict:
        """Turn `think` into Ollama's own option, at the last hop before the call.

        THIS IS WHERE `True` BECOMES AN EFFORT LEVEL — with `cerebras.reasoning_effort`,
        the only place it does. The boolean callers (the evaluation's `Commission`, the
        `generations.think` column, the UI switch) get `config.DEFAULT_THINK_EFFORT`; a
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
        return {"think": config.DEFAULT_THINK_EFFORT if think is True else think}

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
    def _context_option(
        model: str, sampling: Sampling | None = None, max_output_tokens: int | None = None
    ) -> dict:
        """Build the per-call options: the KV cache cap, the sampling and the output cap.

        Left to itself Ollama sizes the KV cache from the model's declared context, which
        is where most of this box's VRAM was going; `config.LLM_CONTEXT` decides it in one
        place so no call site has to know. Both options share one dict, so building them
        apart is how one ends up overwriting the other.

        Only the two generative paths resolve a sampling: `embed`/`embed_batch` call this
        with none and must keep sending none, an embedding having no sampler to steer.
        """
        options: dict = {}
        num_ctx = config.LLM_CONTEXT.get(model)
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        if sampling is not None:
            options["temperature"] = sampling.temperature
            if sampling.top_k is not None:
                options["top_k"] = sampling.top_k
            if sampling.top_p is not None:
                options["top_p"] = sampling.top_p
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        return {"options": options} if options else {}

    @staticmethod
    def _sampling(sampling: Sampling | None) -> Sampling:
        """Resolve a generative call's sampling, never leaving the engine's own 0.8.

        The worst a forgotten argument can do is make a call deterministic.
        """
        return Sampling(config.TEMPERATURE_DEFAULT) if sampling is None else sampling

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

    def _looks_like_embedding(self, model: str) -> bool:
        """Whether `model` has to be unloaded through the embedding endpoint.

        `config.EMBEDDING_MODELS` names the ones this instance uses; `/api/ps` may also
        return one the server loaded on its own, and there the declared capability is the
        only reliable source.
        """
        if model in config.EMBEDDING_MODELS:
            return True
        return "embedding" in self.capabilities(model)

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


def _drain(
    stream, stop_on_loop: bool = False
) -> tuple[str, str, bool, str | None, tuple[int | None, int | None]]:
    """Read a streamed answer whole, checking between chunks whether to stop.

    The counterpart of `progress.checkpoint()` inside every per-item loop: without it the
    smallest interruptible unit is a whole model call, and a call is minutes. The stream is
    closed on the way out so the engine learns its client has gone — that is what turns a
    cancellation into a GPU that is free rather than one still writing an answer nobody
    asked for any more.

    The third value is whether the final chunk says the answer was cut by `num_predict`:
    only that chunk carries a `done_reason`, and "length" there is the engine reporting
    a truncation that the text alone cannot show. The fourth is the unit the answer was
    repeating when `stop_on_loop` made the read stop: the same abandonment as a
    cancellation, for a model that has stopped saying anything new. The fifth is what the
    last chunk says the call cost, the prompt's tokens and the answer's (`usage`); a stream
    left before its end says nothing.
    """
    answer: list[str] = []
    thinking: list[str] = []
    truncated = False
    loop: str | None = None
    tail = ""
    unchecked = 0
    counts: tuple[int | None, int | None] = (None, None)
    try:
        for chunk in stream:
            thought = getattr(chunk, "thinking", None)
            if thought:
                thinking.append(thought)
            piece = chunk.response or ""
            answer.append(piece)
            counts = _counts(chunk, counts)
            if getattr(chunk, "done_reason", None) == "length":
                truncated = True
            if stop_on_loop and piece:
                tail = (tail + piece)[-config.TRANSCRIBE_LOOP_STREAM_WINDOW_CHARS :]
                unchecked += len(piece)
                if unchecked >= config.TRANSCRIBE_LOOP_STREAM_CHECK_CHARS:
                    unchecked = 0
                    found = repetition.detect_tail(tail)
                    if found is not None:
                        loop = found.unit
                        break
            progress.checkpoint()
    finally:
        close = getattr(stream, "close", None)
        if close is not None:
            close()
    return "".join(answer), "".join(thinking), truncated, loop, counts


def _counts(chunk, held: tuple[int | None, int | None]) -> tuple[int | None, int | None]:
    """Return the tokens a chunk says the call cost, or what was held: only the last says."""
    prompt = getattr(chunk, "prompt_eval_count", None)
    answer = getattr(chunk, "eval_count", None)
    if prompt is None and answer is None:
        return held
    return (prompt if isinstance(prompt, int) else held[0], answer if isinstance(answer, int) else held[1])


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
