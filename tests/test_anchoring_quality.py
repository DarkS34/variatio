import json
from pathlib import Path

import pytest

from variant_generator import config
from variant_generator.builders.knowledge_graph_builder import extraction

SOURCES = Path("workspaces/default/cache/concept_sources.json")


def load():
    if not SOURCES.exists():
        pytest.skip(f"no hay {SOURCES}; reconstruye el grafo para medir el anclaje")
    with SOURCES.open(encoding="utf-8") as f:
        return json.load(f)["concepts"]


def entries(concepts):
    return [(name, e) for name, es in concepts.items() for e in es]


@pytest.mark.corpus
def test_almost_every_passage_contains_its_concept():
    rows = entries(load())
    hits = sum(1 for name, e in rows if extraction.mentions(e["text"], name))
    assert hits / len(rows) >= 0.95, f"{hits}/{len(rows)} pasajes contienen su concepto"


@pytest.mark.corpus
def test_no_passage_is_a_table_of_contents():
    offenders = [name for name, e in entries(load()) if extraction.is_navigation(e["text"])]
    assert offenders == []


@pytest.mark.corpus
def test_no_passage_is_shared_by_more_than_three_concepts():
    counts = {}
    for _name, e in entries(load()):
        counts[e["text"]] = counts.get(e["text"], 0) + 1
    assert max(counts.values(), default=0) <= 3


@pytest.mark.corpus
def test_no_passage_is_cut_mid_sentence():
    offenders = [
        name
        for name, e in entries(load())
        if len(e["text"]) >= config.KG_SOURCE_PASSAGE_CHARS - 1
        and not e["text"].rstrip().endswith((".", ":", ")", "!", "?"))
    ]
    assert offenders == []
