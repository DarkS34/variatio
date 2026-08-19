import logging
import sys
import warnings

from loguru import logger

from . import inference
from .config import LOG_LEVEL, NOISY_LOGGERS, NOISY_WARNING_MODULES

for name in NOISY_LOGGERS:
    logging.getLogger(name).setLevel(logging.ERROR)
for pattern in NOISY_WARNING_MODULES:
    warnings.filterwarnings("ignore", module=pattern)


logger.remove()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger.level("DEBUG",   color="<blue><dim>")
logger.level("INFO",    color="<white>")
logger.level("SUCCESS", color="<bold><green>")
logger.level("WARNING", color="<yellow>")
logger.level("ERROR",   color="<bold><red>")

logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    format="[{time:HH:mm:ss}] <level>{level: <8}</level> | <cyan>{module}</cyan> >> {message}",
    colorize=True,
)

def bootstrap() -> None:
    if not inference.is_available():
        msg = f"Cannot connect to inference engine '{inference.engine_name()}'. Make sure it is running before initializing the agent."
        logger.critical(msg)
        raise RuntimeError(msg)