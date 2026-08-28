import inspect

import pytest

from variatio.builders.knowledge_graph_builder import cleaning, curation, extraction


def _binds(fn, *args, **kwargs):
    inspect.signature(fn).bind(*args, **kwargs)
    return True


SENTINEL = object()


def test_the_three_phases_take_the_prompt_set():
    assert _binds(
        extraction.run,
        "corpus",
        converter=None,
        schema=None,
        chunk_size=1,
        cache_dir="cache",
        max_attempts=1,
        prompts=SENTINEL,
        recursive=False,
    )
    assert _binds(cleaning.run, {}, schema=None, max_attempts=1, prompts=SENTINEL)
    assert _binds(
        curation.run, {}, "salida", "fuentes", schema=None, max_attempts=1, prompts=SENTINEL
    )


# `run` hands the set down; the two it calls demand it, and neither takes a default. The
# migration of 2026-08-27 left all three unwired and nothing failed until a real build ran.
@pytest.mark.parametrize(
    "fn, args, kwargs",
    [
        (
            extraction.convert_corpus,
            ("corpus",),
            {"recursive": False, "converter": None, "chunk_size": 1, "cache_dir": "cache"},
        ),
        (extraction.extract_documents, ([],), {"schema": None, "max_attempts": 1}),
        (curation.curate_units, ({},), {"max_attempts": 1}),
    ],
)
def test_every_inner_call_requires_the_prompt_set(fn, args, kwargs):
    with pytest.raises(TypeError):
        inspect.signature(fn).bind(*args, **kwargs)
    assert _binds(fn, *args, **kwargs, prompts=SENTINEL)
