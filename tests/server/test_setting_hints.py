"""The panel's (i) per setting names declared settings, and the measured `doc` never leaves."""

import importlib.util
import re
from pathlib import Path

from variatio import settings
from variatio.settings.registry import BY_KEY

HINTS = Path(__file__).resolve().parents[2] / "web/src/features/admin/hints.ts"


def hinted_keys() -> list[str]:
    """Return the setting keys the client's hint table names."""
    return re.findall(r'^\s+"([a-z_.]+)":\s*$|^\s+"([a-z_.]+)": "cfg\.hint\.', HINTS.read_text(), re.M)


def test_every_hint_names_a_declared_setting():
    keys = [a or b for a, b in hinted_keys()]
    assert keys, "la tabla de pistas no se ha podido leer"
    # The study's settings exist only where `evaluation/` does.
    with_study = importlib.util.find_spec("evaluation") is not None
    missing = [
        key
        for key in keys
        if key not in BY_KEY and (with_study or not key.startswith("evaluation."))
    ]
    assert not missing, f"pistas de ajustes que no existen: {missing}"


def test_the_panel_never_receives_the_measured_doc():
    assert all("doc" not in row for row in settings.snapshot())
