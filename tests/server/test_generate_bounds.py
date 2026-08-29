"""The submit route bounds the commission's count and its free text.

Not tidiness: the count is the one parameter that decides how much a single request
spends, and unbounded it let a commission empty the day's quota before anything could
refuse it — measured against a live installation, an `n: 100000` was accepted, started
running, and was only stopped by an explicit DELETE. The library already knew both rules;
the API simply never asked, so the answer arrived as a failed job after the commission had
taken a lane and raised a `PipelineContext`.
"""

import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from server.routers import jobs
from variatio import config

FORM = Path(__file__).resolve().parents[2] / "web/src/features/run/GenerateForm.tsx"


def refused(params: dict) -> HTTPException:
    with pytest.raises(HTTPException) as error:
        jobs._check_params("generate", params)
    assert error.value.status_code == 422
    return error.value


def test_a_count_within_the_bound_goes_through():
    jobs._check_params("generate", {"n": 1})
    jobs._check_params("generate", {"n": config.GENERATION_MAX_ITEMS})
    jobs._check_params("generate", {})


def test_a_count_above_the_bound_is_refused_before_anything_is_queued():
    detail = refused({"n": 100000}).detail
    assert str(config.GENERATION_MAX_ITEMS) in detail
    assert "100000" in detail


@pytest.mark.parametrize("count", [0, -5])
def test_a_count_below_one_is_refused_here_and_not_in_the_handler(count):
    assert str(count) in refused({"n": count}).detail


@pytest.mark.parametrize("count", ["muchos", [3], {"n": 3}])
def test_a_count_that_is_not_a_number_is_refused_rather_than_crashing(count):
    refused({"n": count})


def test_free_text_over_the_cap_is_refused_with_both_numbers(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_INSTRUCTIONS_MAX_CHARS", 600)
    detail = refused({"instructions": "x" * 10000}).detail
    assert "600" in detail and "10000" in detail


def test_free_text_within_the_cap_goes_through(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_INSTRUCTIONS_MAX_CHARS", 600)
    jobs._check_params("generate", {"instructions": "x" * 600})
    jobs._check_params("generate", {"instructions": None})


# Every other kind carries parameters of its own shape and none of them counts items.
def test_no_other_kind_is_bounded():
    jobs._check_params("build_kg", {"n": 100000, "instructions": "x" * 10000})


# The bound exists twice — here and as the form's own clamp — because the screen cannot ask
# the server what it may offer before the person has typed anything. This keeps the two
# numbers from drifting, the way the slot labels are kept beside the catalogue.
def test_the_bound_matches_what_the_form_already_clamps_to():
    declared = re.search(r"const MAX_ITEMS = (\d+);", FORM.read_text(encoding="utf-8"))
    assert declared, "GenerateForm.tsx no longer declares MAX_ITEMS"
    assert int(declared.group(1)) == config.GENERATION_MAX_ITEMS
