"""The package root: the logging configuration, and nothing else.

Importing `variatio` is side-effect-free apart from the logging setup below, and it must
stay that way: the engine check lives in `core.inference.require_engine()`, which every
entry point that talks to a model calls, so nothing here pulls the ollama SDK, httpx and
tqdm into a caller that only wanted a loader.
"""

import logging
import sys
import warnings

from loguru import logger

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