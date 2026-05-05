import logging
import sys
import warnings

from loguru import logger

from .config import NOISY_LOGGERS, NOISY_WARNING_MODULES
from .utils import cold_start_models, is_ollama_connected

for name in NOISY_LOGGERS:
    logging.getLogger(name).setLevel(logging.ERROR)
for pattern in NOISY_WARNING_MODULES:
    warnings.filterwarnings("ignore", module=pattern)


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

if is_ollama_connected():
    cold_start_models()
else:
    logger.error("Cannot connect to Ollama. Make sure Ollama is running before initializing the agent.")
    exit()