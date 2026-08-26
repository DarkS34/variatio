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

# Imported here and not at module scope: `core.inference` pulls in the ollama SDK, httpx and
# tqdm, which is 364 ms of the 510 ms `import variatio` used to cost — paid by every
# CLI invocation, every test collection and every module that only wanted a loader.
def bootstrap() -> None:
    from .core import inference

    if not inference.is_available():
        msg = f"Cannot connect to inference engine '{inference.engine_name()}'. Make sure it is running before initializing the agent."
        logger.critical(msg)
        raise RuntimeError(msg)
