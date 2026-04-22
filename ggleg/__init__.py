import sys
from loguru import logger
from .utils import is_ollama_connected

logger.remove()

logger.add(
    sys.stderr,
    level="INFO",
    format="[{time:HH:mm:ss}] <level>{level: <8}</level> | <cyan>{module}</cyan> >> {message}",
    colorize=True
)

if not is_ollama_connected():
    logger.error("Cannot connect to Ollama. Make sure Ollama is running before initializing the agent.")
    exit()