import json
from pathlib import Path


class ExemplarsBank:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.bank = self._load(self.path) if self.path.is_file() else None

    @staticmethod
    def _load(path: str | Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
