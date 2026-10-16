"""Importing the library stays light: no engine, no Docling, no torch, no server.

`import variatio` runs on every CLI call and in every build worker, and the engine boundary
alone costs about 220 ms (`variatio/__init__.py`). Each check runs in a fresh interpreter,
because this suite's own imports have already loaded everything.
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

HEAVY = ("variatio.core.inference", "docling", "torch", "server", "fastapi", "sqlalchemy")

# What the settings registry reaches by its optional imports: each function's settings and
# the packages that hold them, never more of a function.
FUNCTION_SETTINGS = {
    "consumers",
    "consumers.chat",
    "consumers.chat.settings",
    "consumers.evaluation",
    "consumers.evaluation.settings",
    "consumers.tutor",
    "consumers.tutor.settings",
}


def _loaded_after(statement: str) -> list[str]:
    code = f"import json, sys; {statement}; print(json.dumps(sorted(sys.modules)))"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=True
    )
    return json.loads(out.stdout)


def test_importing_variatio_loads_no_engine_converter_or_server():
    loaded = _loaded_after("import variatio")
    assert [m for m in HEAVY if m in loaded] == []
    functions = {m for m in loaded if m == "consumers" or m.startswith("consumers.")}
    assert functions <= FUNCTION_SETTINGS, sorted(functions - FUNCTION_SETTINGS)


def test_importing_the_door_and_the_work_loads_no_converter():
    loaded = _loaded_after(
        "import variatio.entrypoints, variatio.builders, variatio.runtime.generator"
    )
    assert [m for m in ("docling", "torch", "server", "fastapi", "sqlalchemy") if m in loaded] == []
