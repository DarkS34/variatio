"""Every step the study emits has a name the browser can translate.

The client names a step by its ID (`lib/names.ts`) and explains it by the same id
(`lib/explain.ts`), never by the label the server sends — so a step id nothing lists
falls through to the server's Spanish string in both languages. That is how
`eval.tagging` shipped nameless on 2026-09-04 and how the RAG index's two slots read as
«el banco» twice; this pins the ids the study emits to the three tables at once.
"""

import re

from study.arms import rag
from study.arms.vector_store import FlatIndex
from variatio.core.paths import PROJECT_ROOT

WEB = PROJECT_ROOT / "web" / "src"

# The ids `progress.step(...)` is called with under `study/`, plus the two the index builds
# under; a new step is added here AND to the three client tables, or the test says which.
STUDY_STEP_IDS = (
    "eval.arms",
    "eval.guardrail",
    "eval.admissibility",
    "eval.tagging",
    *rag._STEP_IDS.values(),
)


def _read(relative: str) -> str:
    return (WEB / relative).read_text(encoding="utf-8")


def test_every_study_step_is_named_in_the_client_tables():
    names = _read("lib/names.ts")
    explain = _read("lib/explain.ts")
    for step in STUDY_STEP_IDS:
        assert re.search(rf'"?{re.escape(step)}"?: "step\.{re.escape(step)}\.label"', names), (
            f"`{step}` has no entry in lib/names.ts"
        )
        assert f'"{step}",' in explain, f"`{step}` has no entry in lib/explain.ts STEP_IDS"


def test_every_study_step_has_a_label_and_an_explanation_in_both_catalogues():
    for catalogue in ("es", "en"):
        text = _read(f"lib/i18n/{catalogue}.ts")
        for step in STUDY_STEP_IDS:
            assert f'"step.{step}.label":' in text, f"`step.{step}.label` missing in {catalogue}"
            assert f'"step.{step}":' in text, f"`step.{step}` missing in {catalogue}"


def test_the_two_rag_indices_are_built_under_two_different_step_ids(monkeypatch, tmp_path):
    """Under one id the two indices are two rows of one name in the run's timeline."""
    monkeypatch.setattr(rag.raw_text, "prepare_slot", lambda ws, slot: None)
    monkeypatch.setattr(rag.raw_text, "chunks", lambda ws, slot, size: {f"{slot}#1": slot})
    monkeypatch.setattr(rag, "_indices", {})

    class _Ws:
        slug = "lab"
        cache_dir = tmp_path

    corpus = rag.index_for(_Ws(), rag.CORPUS)
    exemplars = rag.index_for(_Ws(), rag.EXEMPLARS)
    assert isinstance(corpus, FlatIndex) and isinstance(exemplars, FlatIndex)
    assert corpus.step_id != exemplars.step_id
    assert {corpus.step_id, exemplars.step_id} == set(rag._STEP_IDS.values())
    assert corpus.label != exemplars.label
