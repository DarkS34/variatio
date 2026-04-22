import json
import os
from argparse import ArgumentParser
from pathlib import Path

import httpx
import ollama

PROMPTS_DIR = Path(__file__).parent / "prompts" 


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
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        response = httpx.get(host, timeout=3.0)
        return response.status_code == 200
    except httpx.ConnectError:
        return False


def get_installed_models(with_info: bool = False):
    try:
        if with_info:
            installed_models = [
                installed_model_info for installed_model_info in ollama.list()["models"]
            ]
        else:
            installed_models = [
                installed_model_info["model"]
                for installed_model_info in ollama.list()["models"]
            ]

        return installed_models
    except Exception as e:
        print(e)
        exit()


def download_model(model_name: str) -> bool:
    try:
        download_progress = ollama.pull(model_name, stream=True)
        total = 0
        completed = 0
        for partial_progress in download_progress:
            if 'total' in partial_progress:
                total = partial_progress.get('total', 0)
            if 'completed' in partial_progress:
                completed = partial_progress.get('completed', 0)

            if total > 0 and completed <= total:
                progress = (completed / total) * 100

                print(f"\r {model_name} {progress:.1f}%",flush=True,end="")

        return True
    except (ollama.ResponseError, httpx.RequestError) as e:
        print(f"\n Download failed: {e}")
        return False

def is_model_installed(model_name: str) -> bool:
    if model_name in get_installed_models():
        return True
    else:
        return download_model(model_name)

def load_exercises_dataset(path: str) -> dict:
    exercises_path = Path(__file__).parent / path
    with open(exercises_path, 'r', encoding='utf-8') as f:
        exercises = json.load(f)
    return exercises

def load_prompt(name: str, **kwargs) -> str:
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**kwargs) if kwargs else template
