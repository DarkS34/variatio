import sys
from loguru import logger

from .utils import is_ollama_connected

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>")
# LOG_FILE: str = "logs/system.log"
# logger.add(LOG_FILE, level="DEBUG", rotation="5 MB", retention="7 days", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}")

if not is_ollama_connected():
    logger.error("Cannot connect to Ollama. Make sure Ollama is running before initializing the agent.")
    exit()