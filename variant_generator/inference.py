from collections.abc import Callable
from dataclasses import dataclass

import httpx
import ollama
from loguru import logger
from tqdm import tqdm

from . import config, progress

TokenSink = Callable[[str, str], None]


class InferenceError(Exception):
    pass


@dataclass
class GenerationResponse:
    response: str
    thinking: str | None = None


class OllamaEngine:
    name = "ollama"

    def __init__(self):
        self._client = ollama.Client(host=config.OLLAMA_HOST)
        self._thinking: dict[str, bool] = {}
        self._loaded: str | None = None

    def is_available(self) -> bool:
        try:
            response = httpx.get(config.OLLAMA_HOST, timeout=3.0)
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    # A single GPU cannot hold two 30B models: every switch reloads weights and stalls
    # for seconds. Announce it so the UI shows "loading X" instead of looking frozen.
    def _announce_model(self, model: str, role: str) -> None:
        if self._loaded != model:
            progress.model_loading(model, role)
            self._loaded = model

    def generate(self, model: str, prompt: str, think: bool | None = None) -> GenerationResponse:
        self._announce_model(model, "generation")
        options = {} if think is None else {"think": think}
        try:
            resp = self._client.generate(model=model, prompt=prompt, **options)
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama generation failed for model '{model}': {e}") from e
        return GenerationResponse(
            response=resp.response, thinking=getattr(resp, "thinking", None)
        )

    def generate_stream(
        self,
        model: str,
        prompt: str,
        think: bool | None = None,
        on_token: TokenSink | None = None,
    ) -> GenerationResponse:
        if on_token is None:
            return self.generate(model=model, prompt=prompt, think=think)

        self._announce_model(model, "generation")
        options = {} if think is None else {"think": think}
        answer: list[str] = []
        thinking: list[str] = []
        try:
            for chunk in self._client.generate(
                model=model, prompt=prompt, stream=True, **options
            ):
                thought = getattr(chunk, "thinking", None)
                if thought:
                    thinking.append(thought)
                    on_token(thought, "thinking")
                text = chunk.response
                if text:
                    answer.append(text)
                    on_token(text, "answer")
                # Streaming hands back control on every chunk, which is exactly where a
                # cooperative cancel can take effect without waiting for the full answer.
                progress.checkpoint()
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama generation failed for model '{model}': {e}") from e

        return GenerationResponse(
            response="".join(answer), thinking="".join(thinking) or None
        )

    def supports_thinking(self, model: str) -> bool:
        if model not in self._thinking:
            try:
                capabilities = self._client.show(model).capabilities or []
            except (ollama.ResponseError, httpx.RequestError) as e:
                logger.warning(f"Could not read capabilities of '{model}': {e}")
                capabilities = []
            self._thinking[model] = "thinking" in capabilities
        return self._thinking[model]

    def embed(self, model: str, text: str) -> list[float]:
        self._announce_model(model, "embedding")
        try:
            return self._client.embeddings(model=model, prompt=text)["embedding"]
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama embedding failed for model '{model}': {e}") from e

    def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._announce_model(model, "embedding")
        try:
            return list(self._client.embed(model=model, input=texts)["embeddings"])
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(
                f"Ollama batch embedding failed for model '{model}': {e}"
            ) from e

    def installed_models(self) -> list[str]:
        try:
            return [info["model"] for info in self._client.list()["models"]]
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Could not list Ollama models: {e}") from e

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
        try:
            logger.info(f"Downloading model '{model}'...")
            download_progress = self._client.pull(model, stream=True)

            pbar = None
            for partial_progress in download_progress:
                total = partial_progress.get("total") or 0
                completed = partial_progress.get("completed") or 0

                if total > 0:
                    if pbar is None:
                        pbar = tqdm(total=total, unit="B", unit_scale=True, desc=model)
                    pbar.update(completed - pbar.n)

            if pbar is not None:
                pbar.close()

            logger.success(f"Successfully downloaded model '{model}'")
            return True
        except (ollama.ResponseError, httpx.RequestError) as e:
            logger.error(f"Download failed: {e}")
            return False


_ENGINES = {OllamaEngine.name: OllamaEngine}

_engine = None


def engine():
    global _engine
    if _engine is None:
        if config.INFERENCE_ENGINE not in _ENGINES:
            raise InferenceError(
                f"Unknown inference engine '{config.INFERENCE_ENGINE}'. "
                f"Available: {', '.join(sorted(_ENGINES))}"
            )
        _engine = _ENGINES[config.INFERENCE_ENGINE]()
    return _engine


def engine_name() -> str:
    return config.INFERENCE_ENGINE


def generate(model: str, prompt: str, think: bool | None = None) -> GenerationResponse:
    return engine().generate(model=model, prompt=prompt, think=think)


def generate_stream(
    model: str,
    prompt: str,
    think: bool | None = None,
    on_token: TokenSink | None = None,
) -> GenerationResponse:
    return engine().generate_stream(
        model=model, prompt=prompt, think=think, on_token=on_token
    )


def supports_thinking(model: str) -> bool:
    return engine().supports_thinking(model)


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


def required_models() -> dict[str, str]:
    """The models `config.py` asks for, keyed by the setting that asks for them."""
    return {
        name: value
        for name, value in vars(config).items()
        if name.endswith(("_LLM", "_MODEL")) and isinstance(value, str)
    }


def warmup(model: str, is_embedding: bool = False) -> None:
    engine().warmup(model, is_embedding=is_embedding)
