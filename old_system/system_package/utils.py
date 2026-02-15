import json
import os
import re
import subprocess
from argparse import ArgumentParser
from pathlib import Path

import ollama
import pandas as pd
import requests
from langchain.text_splitter import CharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, ByteSize

from .data_models import ModelInfo, SummarizerConfig


class CustomStringOutputParser(StrOutputParser):
    """Custom parser that removes thinking tags from reasoning model outputs."""

    def parse(self, text: str) -> str:
        """Remove <think>...</think> tags and return clean output."""
        # Check if the text contains thinking tags and remove them
        if self._has_thinking_tags(text):
            cleaned_text = re.sub(r'<think>.*?</think>',
                                  '', text, flags=re.DOTALL | re.IGNORECASE)
            # Clean up extra whitespace that might be left
            # Multiple newlines to double
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)
            cleaned_text = cleaned_text.strip()
            return cleaned_text

        return text

    def _has_thinking_tags(self, text: str) -> bool:
        """Check if text contains thinking tags."""
        return bool(re.search(r'<think>.*?</think>', text, flags=re.DOTALL | re.IGNORECASE))


class EvolutionTextSummarizer:
    def __init__(
        self,
        model: any,
        summary_prompt: str,
        context_window: int,
    ):
        self.model = model
        self.context_window = context_window
        self.config = SummarizerConfig()

        # Determine the token counting function
        self.token_counter = getattr(model, 'get_num_tokens', None)
        if not self.token_counter:
            # Fallback to simple estimation if no token counter is available
            self.token_counter = lambda text: int(
                len(text.split()) * self.config.tokens_per_word)

        # Configure the text splitter
        self.text_splitter = CharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separator=self.config.separator,
            length_function=self.token_counter,
        )

        # Configure the summarization chain
        self.summary_chain = PromptTemplate.from_template(
            summary_prompt) | self.model | CustomStringOutputParser()

    def needs_summarization(self, text: str) -> bool:
        try:
            token_count = self.token_counter(text)
            return token_count > (self.context_window - self.config.safety_margin)
        except Exception as _:
            words = len(text.split())
            estimated_tokens = int(words * self.config.tokens_per_word)
            return estimated_tokens > (self.context_window - self.config.safety_margin)

    def summarize_text(self, text: str, max_recursion: int = 3, current_depth: int = 0) -> str:
        if current_depth >= max_recursion:
            return text

        if not self.needs_summarization(text):
            return text

        try:
            chunks = self.text_splitter.split_text(text)

            summaries: list[str] = []
            for i, chunk in enumerate(chunks, 1):
                try:
                    summary = self.summary_chain.invoke({"chunk": chunk})
                    summaries.append(summary)
                except Exception as _:
                    # Include a simple fallback if summarization failed
                    summaries.append(chunk)

            combined_summary = " ".join(summaries)

            # Check if more summarization is needed
            if self.needs_summarization(combined_summary):
                return self.summarize_text(
                    combined_summary,
                    max_recursion=max_recursion,
                    current_depth=current_depth + 1
                )

            return combined_summary

        except Exception as e:
            raise ValueError(f"Error summarizing text: {str(e)}")


def color_text(text, color="green"):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "cyan": "\033[96m",
    }
    return f"{colors.get(color, '')}[{text}]\033[0m"


def get_exclusion_terms() -> list[str]:
    return [
        # Spanish terms
        "con", "y", "de", "del", "la", "el", "en", "por", "sin", "a", "para",
        "debido", "asociado", "crónico", "agudo",
        "al", "ambos", "ante", "cada", "como", "desde", "ella", "hasta",
        "las", "lo", "los", "que", "se", "según", "sí", "sobre", "su",
        "un", "una", "unas", "uno", "unos",

        # English terms
        "with", "and", "of", "the", "in", "by", "without", "to", "for",
        "due", "associated", "secondary", "primary", "chronic", "acute",
        "at", "both", "before", "each", "as", "from", "she", "until",
        "them", "it", "they", "that", "is", "according", "yes", "on", "his", "her", "its", "their",
        "a", "an", "some", "one", "ones"
    ]


def check_ollama_connection(url: str = "http://localhost:11434") -> None:
    try:
        if not requests.get(url).status_code == 200:
            print(
                f"{color_text('ERROR', 'red')} An error occurred. Unable to connect to Ollama.\n"
            )
            exit(1)
    except requests.ConnectionError:
        print(f"{color_text('ERROR', 'red')} Ollama is not running.")
        exit(1)


def get_context_window_length(model_name: str, desired_context_window: int) -> int:
    try:
        result = subprocess.run(
            ["ollama", "show", model_name],
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.split('\n'):
            line = line.strip()
            if "context length" in line.lower():
                max_context_window = int(line.split()[-1])
                return desired_context_window if desired_context_window <= max_context_window else max_context_window
        return -1
    except subprocess.CalledProcessError as e:
        print(f"Error running ollama show: {e}")
        return -1
    except FileNotFoundError:
        print("Error: ollama command not found. Is it installed and in PATH?")
        return -1


def get_analyzer_configuration(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"File '{path}' not found")

    try:
        config = pd.read_json(path, typ="series").to_dict()
    except ValueError:
        raise ValueError(f"Invalid JSON format in file '{path}'")

    # Verify required fields
    required_fields = ["optimal_model", "models", "prompts"]
    missing_fields = [
        field for field in required_fields if field not in config]
    if missing_fields:
        raise ValueError(
            f"Missing required fields in configuration: {', '.join(missing_fields)}"
        )

    if not config["models"] or len(config["models"]) == 0:
        raise ValueError("The 'models' array cannot be empty")

    if not isinstance(config["prompts"], dict):
        raise ValueError("The 'prompts' field must be a dictionary")

    # Verify required prompts in the new structure
    required_prompts = [
        "gen_summary_prompt",
        "gen_diagnostic_prompt",
        "gen_icd_code_prompt"
    ]
    missing_prompts = [
        prompt for prompt in required_prompts if prompt not in config["prompts"]
    ]
    if missing_prompts:
        raise ValueError(
            f"Missing required prompts: {', '.join(missing_prompts)}")

    # Validate optimal_model
    if not isinstance(config["optimal_model"], int) or not config[
        "optimal_model"
    ] == int(config["optimal_model"]):
        raise ValueError("The 'optimal_model' must be an integer")

    optimal_model_index = int(config["optimal_model"])
    if optimal_model_index < 0 or optimal_model_index >= len(config["models"]):
        raise ValueError(
            f"The 'optimal_model' index ({optimal_model_index}) is out of range for the models array (0-{len(config['models']) - 1})"
        )

    return config
    

def get_args():
    parser = ArgumentParser(
        description="Medical evolution text analyzer with multiple operation modes.",
        allow_abbrev=False
    )
    parser.add_argument(
        "-f", "--filename",
        type=str,
        default="evolution_texts.csv",
        dest="et_filename",
        help="Filename for the evolution texts file"
    )
    parser.add_argument(
        "-m", "--mode",
        type=int,
        choices=[1, 2],
        default=1,
        dest="eval_mode",
        help="Operation mode: 1 for all models, 2 for model selection"
    )
    parser.add_argument(
        "-b", "--batches",
        type=int,
        default=1,
        dest="process_batch",
        help="Number of batches for parallel processing"
    )
    parser.add_argument(
        "-n", "--num-texts",
        type=int,
        default=None,
        dest="num_texts",
        help="Number of texts to process"
    )
    parser.add_argument(
        "-W", "--context-window",
        type=int,
        default=3072,
        dest="selected_context_window",
        help="Change context window size"
    )
    parser.add_argument(
        "-t", "--test",
        action="store_true",
        dest="test_mode",
        help="Run in test mode to evaluate model performance"
    )
    parser.add_argument(
        "-i", "--installed",
        action="store_true",
        dest="only_installed_models_mode",
        help="Only use models that are already installed"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        dest="verbose_mode",
        help="Print detailed output during processing"
    )
    parser.add_argument(
        "-N", "--normalize",
        action="store_true",
        dest="normalization_mode",
        help="Normalize results using custom SNOMED dataset"
    )
    
    args = parser.parse_args()
    
    if args.normalization_mode and not os.path.isfile("snomed_description_icd_normalized.csv"):
        print("The normalization database does NOT exist in the current directory.")
        exit()
    

    return args


def get_evolution_texts(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"File '{path}' not found")

    ext = path.suffix
    with open(path, mode="r", encoding="utf-8") as file:
        if ext == ".csv":
            texts = pd.read_csv(file, sep="|", quotechar="'").to_dict(
                orient="records")
        elif ext == ".json":
            texts = pd.read_json(file)
        else:
            print(
                f"{color_text('ERROR', 'red')} Extension not supported. Must be .json or .csv"
            )
            exit(1)

    required_fields = ["id", "evolution_text"]
    for i, evolution_text in enumerate(texts):
        missing_fields = [
            field for field in required_fields if field not in evolution_text
        ]
        if missing_fields:
            raise ValueError(
                f"Missing required fields {missing_fields} in record {i}")

        evolution_text["evolution_text"] = evolution_text["evolution_text"].replace(
            "\n", " "
        )

    return texts


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
        print(color_text("ERROR", "red"), e)
        exit(1)


def model_installed(model_name: str) -> bool:
    if model_name in get_installed_models():
        return True
    else:
        return _download_model(model_name)


def _get_model_info(model_name: str) -> ModelInfo:
    installed_model_info = next(
        (
            installed_model_name
            for installed_model_name in get_installed_models(True)
            if installed_model_name["model"] == model_name
        ),
        None,
    )

    size, parameter_size, quant_level = None, None, None

    if installed_model_info:
        size = (
            f"{round(ByteSize(installed_model_info.get('size', 0)).to('GB'), 1)} GB"
            if "size" in installed_model_info
            else None
        )
        details = installed_model_info.get("details", {})
        parameter_size = details.get("parameter_size")
        quant_level = details.get("quantization_level")

    return ModelInfo(
        model_name=model_name,
        installed=bool(installed_model_info),
        size=size,
        parameter_size=parameter_size,
        quantization_level=quant_level,
    )


def get_listed_models_info(
    listed_model_names: list[str], installed_only: bool = False
) -> list[ModelInfo]:
    if not listed_model_names:
        print(f"{color_text('ERROR', 'red')} No models found in config list")
        exit(1)

    models = [
        _get_model_info(listed_model_name) for listed_model_name in listed_model_names
    ]

    return (
        [model for model in models if model.installed] if installed_only else models
    )


def _download_model(model_name: str) -> bool:
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

                print(
                    f"\r{color_text('DOWNLOADING', 'cyan')} {model_name} {progress:.1f}%",
                    flush=True,
                    end=""
                )

        return True
    except (ollama.ResponseError, requests.RequestException) as e:
        print(f"\n{color_text('ERROR', 'red')} Download failed: {e}")
        return False


def _display_models_table(models: list[ModelInfo]) -> None:
    col_widths = {
        "name": max(len(model.model_name) for model in models) + 4,
        "available": len("Not installed") + 4,
        "details": 15,
    }

    header = (
        f"\r{'ID'.rjust(4)}  "
        f"{'NAME'.ljust(col_widths['name'])}"
        f"{'AVAILABLE'.ljust(col_widths['available'])}"
        f"{'SIZE'.ljust(col_widths['details'] - 5)}"
        f"{'PARAMETERS'.ljust(col_widths['details'])}"
        f"{'QUANTIZATION'.ljust(col_widths['details'])}"
    )
    print(header)

    for i, model in enumerate(models, 1):
        details = (
            (
                "Installed".ljust(col_widths["available"])
                + f"{model.size or ''}".ljust(col_widths["details"] - 5)
                + f"{model.parameter_size or ''}".ljust(col_widths["details"])
                + f"{model.quantization_level or ''}".ljust(col_widths["details"])
            )
            if model.installed
            else "Not installed"
        )

        print(
            f"{str(i).rjust(4)}. {model.model_name.ljust(col_widths['name'])}{details}"
        )


def choose_model(model_names: list[str], installed_only: bool = False) -> ModelInfo:
    listed = get_listed_models_info(model_names, installed_only)
    if not listed:
        print(f"{color_text('ERROR', 'red')} No models available to choose from.")
        exit(1)

    _display_models_table(listed)
    while True:
        choice = input(f"\nSelect model (1 - {len(listed)}): ").strip()

        if choice.isnumeric() and 1 <= int(choice) <= len(listed):
            selected_model = listed[int(choice) - 1]
            if model_installed(selected_model.model_name):
                return selected_model

        print(
            f"{color_text('ERROR', 'red')} Invalid selection. Please try again.")


def print_evaluated_results(model: dict, results: BaseModel, verbose: bool) -> None:
    print(f"\r{' ' * os.get_terminal_size().columns}", end="", flush=True)
    if verbose:
        for id, evaluated_text in results.evaluated_texts.items():
            print(
                f"\n{id} - {color_text(evaluated_text.valid, 'green' if evaluated_text.valid else 'red')}\n"
                f"\tModel diagnostic: {evaluated_text.processed_output.principal_diagnostic} (Code - {evaluated_text.processed_output.icd_code})\n"
                f"\tCorrect diagnostic: {evaluated_text.correct_diagnostic}"
            )
            if evaluated_text.processed_output.processing_error:
                print(
                    f"\tProcessing Error: {evaluated_text.processed_output.processing_error}"
                )
            if evaluated_text.processed_output.validation_error:
                print(
                    f"\tValidation Error: {evaluated_text.processed_output.validation_error}"
                )
    print()

    performance = results.performance
    accuracy = performance.accuracy
    incorrect = performance.incorrect_outputs
    errors = performance.errors
    total = performance.total_texts

    print(
        f"\rModel: {model.model_name}\n"
        f"Performance:\n"
        f"\t{color_text('Accuracy')}: {accuracy}% ({int((accuracy / 100) * total)}/{total})\n"
        f"\t{color_text('Incorrect outputs', 'red')}: {incorrect}% ({int((incorrect / 100) * total)}/{total})\n"
        f"\tErrors: {errors}% ({int((errors / 100) * total)}/{total})\n\n"
        f"\tTotal records processed: {total}\n"
        f"\tDuration: {performance.duration} s.",
        end="\n",
        flush=True,
    )


def write_results(results_path: str, results: dict) -> None:
    with open(results_path, mode="w", encoding="utf-8") as file:
        json.dump(results, file, indent=3, ensure_ascii=False)

    print(
        f"\r{color_text('COMPLETED')} Results available at:\n{results_path}", end="\n\n"
    )


def print_execution_progression(
    model_name: str,
    processed_texts: int,
    total_texts: int,
    test_mode: bool,
) -> None:
    print(f"\r{' ' * os.get_terminal_size().columns}", end="", flush=True)

    activity_str = 'TESTING' if test_mode else 'PROCESSING'

    print(
        f"\r{color_text(activity_str)} {model_name} - Evolution texts processed {processed_texts}/{total_texts}",
        end="",
        flush=True,
    )
