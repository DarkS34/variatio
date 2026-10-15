"""`apps` imports `variatio` and `server`, and neither of them imports `apps` back.

The settings registry is the library's one exception, and optional: it reaches each
function's settings by name, so their declarations live beside the code that reads them. On
the server, the composition root mounts every function (`server/app.py`), and four reads of
the evaluation older than `apps/` stay where they were, named here so no fifth one grows.
A function's library half stays a library: importing it pulls neither FastAPI nor the
database.
"""

import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# What `variatio/` may import of `apps`, and only inside a `try`: the registry's settings.
LIBRARY_ALLOWED = {pathlib.Path("variatio/settings/registry/__init__.py")}

# What `server/` may import of `apps`, module by module.
SERVER_ALLOWED: dict[pathlib.Path, set[str]] = {
    # The composition root: every function's `install`.
    pathlib.Path("server/app.py"): {
        "apps.chat",
        "apps.evaluation",
        "apps.generation",
        "apps.tutor",
    },
    # An evaluation's two local proposals reserve the lane of the evaluation's own model.
    pathlib.Path("server/jobs/lanes.py"): {"apps.evaluation"},
    # A transcription prepares the evaluation's plain reading of the same slot.
    pathlib.Path("server/jobs/handlers.py"): {"apps.evaluation"},
    pathlib.Path("server/raw_data.py"): {"apps.evaluation"},
    # «Cuentas» counts what each account evaluated.
    pathlib.Path("server/routers/admin.py"): {"apps.evaluation.api"},
}


def _imported_modules(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def _apps_imported(path: pathlib.Path) -> set[str]:
    return {name for name in _imported_modules(path) if name == "apps" or name.startswith("apps.")}


def test_the_library_names_the_functions_only_in_the_registry():
    naming = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "variatio").rglob("*.py")
        if _apps_imported(path) and path.relative_to(ROOT) not in LIBRARY_ALLOWED
    )
    assert naming == [], f"importan una función: {naming}"


def test_the_registry_exceptions_are_optional():
    source = (ROOT / "variatio/settings/registry/__init__.py").read_text(encoding="utf-8")
    assert "try:" in source and "except ImportError" in source
    assert "except ModuleNotFoundError" in source


def test_the_server_imports_the_functions_only_where_this_file_says():
    offenders = []
    for path in sorted((ROOT / "server").rglob("*.py")):
        relative = path.relative_to(ROOT)
        allowed = SERVER_ALLOWED.get(relative, set())
        extra = sorted(name for name in _apps_imported(path) if name not in allowed)
        if extra:
            offenders.append(f"{relative.as_posix()}: {extra}")
    assert not offenders, f"el servidor importa una función fuera de su sitio: {offenders}"


def test_importing_a_function_s_library_half_does_not_pull_the_server_stack():
    code = (
        "import sys, apps, apps.evaluation, apps.evaluation.run, apps.evaluation.config,"
        " apps.tutor, apps.tutor.turn, apps.tutor.criteria_builder, apps.generation,"
        " apps.chat, apps.chat.turn, apps.chat.config;"
        "print(sorted(m for m in ('fastapi', 'sqlalchemy', 'apps.tutor.api',"
        " 'apps.evaluation.api', 'apps.generation.api', 'apps.chat.api') if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=True
    )
    assert out.stdout.strip() == "[]", out.stdout
