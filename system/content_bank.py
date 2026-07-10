import json
from pathlib import Path

from loguru import logger

from system import config


class ContentBank:
    def __init__(self, path: str | Path = config.CONTENT_BANK_PATH):
        self.path = Path(path)
        self.bank = self._load(self.path) if self.path.is_file() else None

    @staticmethod
    def _load(path: str | Path) -> dict:
        with open(path, encoding="utf-8") as f:
            bank = json.load(f)
        logger.info(f"Content bank loaded ({len(bank)} item(s))")
        return bank
