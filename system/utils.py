import importlib.util
import json

import httpx
import ollama
from loguru import logger
from pydantic import BaseModel
from tqdm import tqdm

from . import config


class Manifest(BaseModel):
    context: dict = {}
    item_model: type[BaseModel]
    generation_rules: list[str] = []


def load_manifest(path: str) -> Manifest:
    spec = importlib.util.spec_from_file_location("manifest", path)

    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"Cannot load manifest at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    manifest = Manifest(
        context=getattr(module, "CONTEXT", {}),
        item_model=module.ContentItem,
        generation_rules=list(getattr(module, "GENERATION_RULES", [])),
    )

    logger.success("Manifest loaded")
    return manifest


def cold_start_models() -> None:
    _all_models = [
        config.CONTENT_CLEANING_LLM,
        config.CONTENT_FORMATTING_LLM,
        config.EMBEDDING_LLM,
        config.CONCEPT_TAGGER_LLM,
        config.REPAIR_LLM,
    ]

    logger.info("Initializing models...")
    failed = [m for m in _all_models if not is_model_installed(m)]
    if failed:
        raise RuntimeError(f"Failed to install model(s): {', '.join(failed)}")

    for m in set(_all_models):
        ollama.generate(m) if m != config.EMBEDDING_LLM else ollama.embed(m)

    logger.success("All models ready")


def is_ollama_connected() -> bool:
    try:
        response = httpx.get(config.OLLAMA_HOST, timeout=3.0)
        return response.status_code == 200
    except httpx.ConnectError:
        return False


def _download_model(model_name: str) -> bool:
    try:
        logger.info(f"Downloading model '{model_name}'...")
        download_progress = ollama.pull(model_name, stream=True)

        pbar = None
        for partial_progress in download_progress:
            total = partial_progress.get("total") or 0
            completed = partial_progress.get("completed") or 0

            if total > 0:
                if pbar is None:
                    pbar = tqdm(total=total, unit="B", unit_scale=True, desc=model_name)
                pbar.update(completed - pbar.n)

        pbar.close()

        logger.success(f"Successfully downloaded model '{model_name}'")
        return True
    except (ollama.ResponseError, httpx.RequestError) as e:
        logger.error(f"Download failed: {e}")
        return False


def is_model_installed(model_name: str) -> bool:
    installed_models = [
        installed_model_info["model"] for installed_model_info in ollama.list()["models"]
    ]
    return True if model_name in installed_models else _download_model(model_name)


def json_repair(
    broken_json: str, repair_model: str = config.REPAIR_LLM, error: str = "", max_attempts: int = 5
):
    from .prompts import json_repair as _repair_prompt

    response = ollama.generate(
        model=repair_model, prompt=_repair_prompt(broken_json, error or "invalid JSON")
    ).response

    for attempt in range(1, max_attempts + 1):
        try:
            result = json.loads(response)
            logger.info(f"JSON repaired in {attempt} attempt(s)")
            return result
        except json.JSONDecodeError as parse_err:
            if attempt < max_attempts:
                logger.debug(f"Repair attempt {attempt}/{max_attempts} failed: {parse_err}")
                response = ollama.generate(
                    model=repair_model,
                    prompt=f"Invalid JSON — {parse_err}. Return only valid JSON:\n\n{response}",
                ).response

    logger.warning("Failed to repair JSON, returning empty list")
    return []
