import sys
from loguru import logger
from .utils import is_ollama_connected

logger.remove()

logger.level("DEBUG",   color="<blue><dim>")
logger.level("INFO",    color="<white>")
logger.level("SUCCESS", color="<bold><green>")
logger.level("WARNING", color="<yellow>")
logger.level("ERROR",   color="<bold><red>")

logger.add(
    sys.stdout,
    level="DEBUG",
    format="[{time:HH:mm:ss}] <level>{level: <8}</level> | <cyan>{module}</cyan> >> {message}",
    colorize=True,
)

if not is_ollama_connected():
    logger.error("Cannot connect to Ollama. Make sure Ollama is running before initializing the agent.")
    exit()