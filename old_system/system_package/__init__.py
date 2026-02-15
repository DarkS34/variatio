from .utils import (
    check_ollama_connection,
    get_analyzer_configuration,
    get_args,
    model_installed,
    get_evolution_texts,
    write_results
)
from .tester import AnalyzerTester
from .analyzer import Analyzer
import os

__version__ = "0.1.0"

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


__all__ = [
    "Analyzer",
    "AnalyzerTester",
    "check_ollama_connection",
    "get_analyzer_configuration",
    "get_args",
    "model_installed",
    "get_evolution_texts",
    "write_results"
]
