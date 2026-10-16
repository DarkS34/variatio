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
    out = subprocess.run([str(linter)], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout[-4000:]
