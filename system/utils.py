import json
import os
from pathlib import Path

import httpx
import ollama
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from loguru import logger
import requests
from tqdm import tqdm

OLLAMA_HOST = f"http://{os.environ.get('OLLAMA_HOST', 'localhost:13434')}"

PROMPTS_DIR = Path(__file__).parent / "internal_config" / "prompts" 
MODELS_CONFIG = Path(__file__).parent / "internal_config" / "models.json"

def load_models():
    with open(MODELS_CONFIG, encoding="utf-8") as f:
        models_config: dict = json.load(f)

    if not is_model_installed(models_config["embedding"]):
        logger.critical(f"Failed to install embedding model {models_config['embedding']}")
        exit()
    
    embedding_LLM = OllamaEmbeddings(model=models_config.pop("embedding"))
    
    logger.info("Initializing models")
    
    generative_LLMs = {}
    for role, model_info in models_config.items():
        if not is_model_installed(model_info["model_name"]):
            logger.critical(f"Failed to install model '{str(model_info)}' for role '{role}'")
            exit()
        llm = OllamaLLM(model=model_info["model_name"], format=model_info["format"], reasoning=False, keep_alive=-1)
        requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": model_info["model_name"], "keep_alive": -1},
            timeout=300,
        )
        generative_LLMs[role] = llm

    logger.success("All models initialized correctly")
    
    return {"embedding": embedding_LLM, **generative_LLMs}
    


def is_ollama_connected() -> bool:
    try:
        response = httpx.get(OLLAMA_HOST, timeout=3.0)
        return response.status_code == 200
    except httpx.ConnectError:
        return False

def download_model(model_name: str) -> bool:
    try:
        logger.info(f"Downloading model '{model_name}'...")
        download_progress = ollama.pull(model_name, stream=True)

        pbar = None
        for partial_progress in download_progress:
            total = partial_progress.get('total') or 0
            completed = partial_progress.get('completed') or 0

            if total > 0:
                if pbar is None:
                    pbar = tqdm(total=total, unit='B', unit_scale=True, desc=model_name)
                pbar.update(completed - pbar.n)

        pbar.close()

        logger.success(f"Successfully downloaded model '{model_name}'")
        return True
    except (ollama.ResponseError, httpx.RequestError) as e:
        logger.error(f"Download failed: {e}")
        return False

def is_model_installed(model_name: str) -> bool:
    installed_models = [installed_model_info["model"] for installed_model_info in ollama.list()["models"]]
    
    return True if model_name in installed_models else download_model(model_name)

def load_prompt(name: str, **kwargs) -> str:
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**kwargs) if kwargs else template
