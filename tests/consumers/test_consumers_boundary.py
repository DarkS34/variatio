"""`consumers` imports `variatio` and `server`, and neither of them imports `consumers` back.

Which modules may name a function is a set of import contracts (`[tool.importlinter]` in
`pyproject.toml`, run by `tests/boundaries/test_import_contracts.py`). What a contract cannot
see stays here: that the settings registry, the library's one exception, reaches the
functions only inside a `try`, so the library still imports with a function missing; and that
a function's library half stays a library, so importing it pulls neither FastAPI nor the
database.
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_the_registry_exceptions_are_optional():
    source = (ROOT / "variatio/settings/registry/__init__.py").read_text(encoding="utf-8")
    assert "try:" in source and "except ImportError" in source
    assert "except ModuleNotFoundError" in source


def test_importing_a_function_s_library_half_does_not_pull_the_server_stack():
    code = (
        "import sys, variatio.functionalities, variatio.functionalities.evaluation, variatio.functionalities.evaluation.run,"
        " variatio.functionalities.evaluation.config, variatio.functionalities.tutor, variatio.functionalities.tutor.turn,"
        " variatio.functionalities.tutor.criteria_builder, variatio.functionalities.generation,"
        " variatio.functionalities.chat, variatio.functionalities.chat.turn, variatio.functionalities.chat.config;"
        "print(sorted(m for m in ('fastapi', 'sqlalchemy', 'server.functionalities.tutor',"
        " 'server.functionalities.evaluation', 'server.functionalities.generation', 'server.functionalities.chat')"
        " if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=True
    )
    assert out.stdout.strip() == "[]", out.stdout
