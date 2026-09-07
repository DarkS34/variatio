"""The label `ensure_models` interpolates has to be English, because the sentence is."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "variatio"
CALLERS = [
    "builders/exemplars_bank_builder.py",
    "builders/exemplars_profile_builder.py",
    "builders/knowledge_graph_builder/__init__.py",
]
# An English noun phrase: ASCII lowercase words. It is not a style rule — the label lands
# inside "Checking the {label} models", and a Spanish genitive produced "Checking the del
# perfil de ejemplares models", which is neither language and reached the run drawer.
ENGLISH_NOUN_PHRASE = re.compile(r"^[a-z]+(?: [a-z]+)*$")


def labels_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name != "ensure_models" or len(node.args) < 2:
            continue
        label = node.args[1]
        assert isinstance(label, ast.Constant), f"{path.name}: the label is not a literal"
        found.append(label.value)
    return found


@pytest.mark.parametrize("relative", CALLERS)
def test_every_caller_passes_an_english_noun_phrase(relative):
    labels = labels_of(ROOT / relative)
    assert labels, f"{relative} no longer calls ensure_models"
    for label in labels:
        assert ENGLISH_NOUN_PHRASE.match(label), f"{relative}: «{label}» is not English"


def test_the_three_builders_are_the_only_callers():
    calling = [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*.py")
        if "ensure_models(" in path.read_text(encoding="utf-8")
        and path.name != "inference.py"
    ]
    assert sorted(calling) == sorted(CALLERS)
