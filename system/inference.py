from dataclasses import dataclass

import httpx
import ollama
from loguru import logger
from tqdm import tqdm

from . import config


class InferenceError(Exception):
    pass


@dataclass
class GenerationResponse:
    response: str
    thinking: str | None = None


class OllamaEngine:
    name = "ollama"

    def is_available(self) -> bool:
        try:
            response = httpx.get(config.OLLAMA_HOST, timeout=3.0)
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    def generate(self, model: str, prompt: str, think: bool | None = None) -> GenerationResponse:
        options = {} if think is None else {"think": think}
        try:
            resp = ollama.generate(model=model, prompt=prompt, **options)
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama generation failed for model '{model}': {e}") from e
        return GenerationResponse(
            response=resp.response, thinking=getattr(resp, "thinking", None)
        )

    def embed(self, model: str, text: str) -> list[float]:
        try:
            return ollama.embeddings(model=model, prompt=text)["embedding"]
        except (ollama.ResponseError, httpx.RequestError) as e:
            raise InferenceError(f"Ollama embedding failed for model '{model}': {e}") from e

    def ensure_model(self, model: str) -> bool:
        installed = [info["model"] for info in ollama.list()["models"]]
        if model in installed:
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
            download_progress = ollama.pull(model, stream=True)

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


def embed(model: str, text: str) -> list[float]:
    return engine().embed(model=model, text=text)


def is_available() -> bool:
    return engine().is_available()


def ensure_model(model: str) -> bool:
    return engine().ensure_model(model)


def warmup(model: str, is_embedding: bool = False) -> None:
    engine().warmup(model, is_embedding=is_embedding)
