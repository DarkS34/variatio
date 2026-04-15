from argparse import ArgumentParser

from loguru import logger
from markitdown import MarkItDown
from pathlib import Path

import ollama
import httpx
import os
import json


class ExerciseFormatter:
    def __init__(self):
        self.markitdown = MarkItDown()


    def convert_file(self, input_file_path: str, output_file_path: str):
        input_file_path = Path(input_file_path)
        output_file_path = Path(output_file_path)

        output_md_path = output_file_path.with_suffix(".md")
        result = self.markitdown.convert(str(input_file_path))
        output_md_path.write_text(result.text_content, encoding="utf-8")

        logger.info(f"Converted: {input_file_path.name} --> {output_md_path}")


    def convert_dir(self, input_dir, output_dir):
        input_dir_path = Path(input_dir)
        output_dir_path = Path(output_dir)

        output_dir_path.mkdir(exist_ok=True)

        files = sorted(input_dir_path.glob("*.(pdf|docx)"))

        if not files:
            logger.error("No PDF or WORD files found in the input directory")
        else:
            for file_path in files:
                output_path = output_dir_path / file_path.with_suffix(".md").name
                result = self.markitdown.convert(str(file_path))
                output_path.write_text(result.text_content, encoding="utf-8")
                logger.info(f"Converted: {file_path.name} --> {output_path}")




def get_args():
    parser = ArgumentParser(
        allow_abbrev=False
    )
    
    parser.add_argument(
        "-f", "--filename",
        type=str,
        default="input.txt",
        help="Filename for the evolution texts file"
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
