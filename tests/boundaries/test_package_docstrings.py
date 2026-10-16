"""Every package says what it holds, in the docstring of its `__init__.py`.

The docstring is a package's front page (`ARCHITECTURE.md` sends a reader there), so a
package without one is a folder nobody can place.
"""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_every_package_has_a_docstring():
    missing = sorted(
        init.relative_to(ROOT).as_posix()
        for top in ("variatio", "server", "consumers")
        for init in (ROOT / top).rglob("__init__.py")
        if not ast.get_docstring(ast.parse(init.read_text(encoding="utf-8")))
    )
    assert missing == [], f"paquetes sin docstring: {missing}"
