import os
from pathlib import Path


# A real environment variable always wins: the file is the convenience, the export is
# the deliberate override. Only secrets and host settings live here — never a model
# name or a threshold, which belong in the registry where they can be reviewed in git.
def load_dotenv(path: str | Path) -> None:
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
