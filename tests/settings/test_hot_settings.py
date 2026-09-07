"""No editable setting may be frozen in a default argument.

A default is evaluated once, when the `def` statement runs at import, so
`def f(x=config.X)` pins `X` for the life of the process. The panel then reports a change
it cannot deliver: an `Impact.NONE` setting promises to apply at once, and even
`Impact.CONTEXTS` does not help, because rebuilding the pipeline context constructs new
objects whose defaults are still the ones bound at import.

This is the same failure the "read `config.X` by module attribute" rule exists to prevent;
`from ..config import X` is merely its more obvious form.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREES = ("variatio", "server", "evaluation")


def _frozen_defaults() -> list[str]:
    """Every function default whose expression reads a `config` attribute."""
    found = []
    for tree in TREES:
        for path in sorted((ROOT / tree).rglob("*.py")):
            source = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(source):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d]
                for default in defaults:
                    rendered = ast.unparse(default)
                    if rendered.startswith("config.") or ".config." in rendered:
                        rel = path.relative_to(ROOT)
                        found.append(f"{rel}:{node.lineno} {node.name}(… = {rendered})")
    return found


def test_no_config_value_is_frozen_in_a_default_argument():
    frozen = _frozen_defaults()
    assert frozen == [], (
        "these defaults bind at import and cannot follow a setting the panel edits; "
        "take `None` and resolve `config.X` inside the body:\n  " + "\n  ".join(frozen)
    )
