"""The import boundaries hold: every contract of `[tool.importlinter]` is kept.

The contracts live in `pyproject.toml`, each exception named beside it. Running them here
means `uv run pytest` alone fails when a boundary breaks.
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_every_import_contract_is_kept():
    linter = pathlib.Path(sys.executable).with_name("lint-imports")
    # The cache trusts a file's mtime, so a file restored with an older one is read stale; the
    # whole graph takes 0.4 s to build without it.
    out = subprocess.run([str(linter), "--no-cache"], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout[-4000:]
