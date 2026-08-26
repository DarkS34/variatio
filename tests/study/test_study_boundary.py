import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# The one deliberate exception, taken by explicit user request: the settings registry
# reaches `study.settings` by name so the six declarations live beside the code that reads
# them. It is optional (`try/except ImportError`) and it is the ONLY place. Everywhere else
# the direction is absolute — the study imports the pipeline, the pipeline does not know it
# exists.
ALLOWED = {pathlib.Path("variant_generator/settings/registry/__init__.py")}


def _imported_modules(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def test_the_pipeline_does_not_import_the_study():
    offenders = []
    for path in sorted((ROOT / "variant_generator").rglob("*.py")):
        relative = path.relative_to(ROOT)
        if relative in ALLOWED:
            continue
        if any(name == "study" or name.startswith("study.") for name in _imported_modules(path)):
            offenders.append(relative.as_posix())
    assert not offenders, f"importan el estudio: {offenders}"


def test_the_registry_exception_is_optional():
    source = (ROOT / "variant_generator/settings/registry/__init__.py").read_text(encoding="utf-8")
    assert "try:" in source and "except ImportError" in source


# The same property the builders' Docling rule has: a runtime-only consumer importing the
# study gets the three arms and nothing of the server.
def test_importing_the_study_does_not_pull_the_server():
    code = (
        "import study, study.run, study.config; import sys;"
        "print(sorted(m for m in ('fastapi', 'sqlalchemy') if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=True
    )
    assert out.stdout.strip() == "[]", out.stdout
