"""Read a `.env` file into the process environment, with no dependency."""

import os
from pathlib import Path


def load_dotenv(path: str | Path) -> None:
    """Set every `KEY=VALUE` of `path` that the environment does not already define.

    A real environment variable always wins: the file is the convenience, the export the
    deliberate override. Only secrets and host settings belong here — a model name or a
    threshold belongs in the registry, where it can be reviewed in git.
    """
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
