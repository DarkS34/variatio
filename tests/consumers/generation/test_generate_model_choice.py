"""A commission's model is checked against what is offered before it is queued.

Two layers on purpose, exactly as a raw document's filename is checked against the files
the slot actually holds and then again in the library: here it is a 422 the screen shows
while the person is still looking at the form, and in `handle_generate` it is the last
word, because the offered list is edited from the panel while jobs sit in the queue.
"""

import pytest
from fastapi import HTTPException

from consumers.generation.api import limits
from variatio import config


@pytest.fixture(autouse=True)
def offered(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["el-rapido", "el-que-delibera"])


def test_a_commission_may_name_any_offered_model():
    limits.check({"model": "el-que-delibera"})


def test_a_commission_that_names_none_is_the_normal_case():
    limits.check({"n": 2})
    limits.check({})


def test_a_model_nobody_offers_is_refused_with_the_list():
    with pytest.raises(HTTPException) as error:
        limits.check({"model": "el-de-otra-instalacion"})
    assert error.value.status_code == 422
    assert "el-rapido" in error.value.detail
