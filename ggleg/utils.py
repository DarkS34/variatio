import json
import os
from argparse import ArgumentParser
from pathlib import Path

import httpx
import ollama
from langchain_ollama import OllamaLLM
from loguru import logger
from tqdm import tqdm

PROMPTS_DIR = Path(__file__).parent / "config" / "prompts" 
MODELS_CONFIG = Path(__file__).parent / "config" / "models.json" 

class ModelRegistry:
    def __init__(self, ):
        with open(MODELS_CONFIG, encoding="utf-8") as f:
            self._config: dict[str, str] = json.load(f)

        self._llms: dict[str, OllamaLLM] = {}
        self._embeddings: dict[str, str] = {}

        self._initialize()

    def _initialize(self) -> None:
        for role, model_name in self._config.items():
            if not is_model_installed(model_name):
                raise RuntimeError(f"Failed to install model '{model_name}' for role '{role}'")

            if "embed" in role.lower():
                ollama.embed(model=model_name, input="")
                self._embeddings[role] = model_name
            else:
                llm = OllamaLLM(model=model_name)
                llm.invoke("hi")
                self._llms[role] = llm
        logger.success("All models initialized correctly")

    def llm(self, role: str) -> OllamaLLM:
        if role not in self._llms:
            logger.critical(f"No LLM registered for role '{role}'")
            exit()
        return self._llms[role]

    def embedding(self, role: str) -> str:
        if role not in self._embeddings:
            logger.critical(f"No embedding model registered for role '{role}'")
            exit()
        return self._embeddings[role]


def get_args():
    parser = ArgumentParser(
        allow_abbrev=False
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        dest="verbose_mode",
        help="Print detailed output during processing"
    )

    args = parser.parse_args()

    return args

def is_ollama_connected() -> None:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:13434")
    try:
        response = httpx.get(f"http://{host}", timeout=3.0)
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


def load_exercises_dataset(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        exercises = json.load(f)
    return exercises

def load_prompt(name: str, **kwargs) -> str:
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**kwargs) if kwargs else template
