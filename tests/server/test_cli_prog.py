from importlib.metadata import entry_points

import pytest

from server.cli.common import PROG

TARGET = "server.cli:main"


def declared_scripts() -> list[str]:
    return [
        ep.name
        for ep in entry_points(group="console_scripts")
        if ep.value.replace(" ", "") == TARGET
    ]


def test_prog_names_a_console_script_that_exists():
    declared = declared_scripts()
    if not declared:
        pytest.skip(f"'{TARGET}' is not installed as a console script")
    assert PROG in declared
