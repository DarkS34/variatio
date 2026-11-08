"""No generic prompt names a subject (plan §0, written 2026-11-02 in F14).

The prompts serve any subject, so a word of one subject — a language, a keyword, a topic —
in their text teaches the model that subject. Examples must be abstract, drawn from three
families, or put in by code from the subject's own data. Only string literals are read:
docstrings and comments may name what was measured. The transcription prompts are out of
the tuning (P7) and keep their examples until it is reopened.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULES = sorted(
    [*ROOT.glob("variatio/prompts/*/*.py"), *ROOT.glob("consumers/*/prompts/*.py"),
     ROOT / "variatio/prompts/conversation.py"]
)
# The transcription's prompts (P7) and the tutor's pattern tables, which are vocabulary.
EXEMPT_FUNCTIONS = {"transcribe_page_prompt", "transcribe_image_prompt", "transcribe_retry_note", "merge_pages_prompt"}
EXEMPT_NAMES = {"EVERYDAY_WORDS", "VALIDATION_PATTERN", "REVIEW_PATTERN", "POINTING_PATTERN", "NORMATIVE_PATTERN"}
SUBJECT_WORDS = re.compile(
    r"\b(?:python|pascal|java|javascript|vhdl|recursividad|recursi[oó]n|recursion|len|fibonacci|"
    r"factorial|warfarina|warfarin)\b",
    re.IGNORECASE,
)


def _literals(tree: ast.AST) -> list[tuple[int, str]]:
    """Every string literal outside docstrings, exempt functions and exempt tables."""
    found = []
    skipped: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                skipped.add(id(body[0].value))
            if isinstance(node, ast.FunctionDef) and node.name in EXEMPT_FUNCTIONS:
                skipped |= {id(n) for n in ast.walk(node)}
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in EXEMPT_NAMES for t in targets):
                skipped |= {id(n) for n in ast.walk(node)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skipped:
            found.append((node.lineno, node.value))
    return found


@pytest.mark.parametrize("path", MODULES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_generic_prompt_names_a_subject(path):
    hits = [
        f"{path.name}:{line}: {match.group(0)}"
        for line, text in _literals(ast.parse(path.read_text()))
        for match in SUBJECT_WORDS.finditer(text)
    ]
    assert not hits, hits
