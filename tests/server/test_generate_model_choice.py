"""The submit route checks the model a commission names against what is offered.

Two layers on purpose, exactly as a raw document's filename is checked against the files
the slot actually holds and then again in the library: here it is a 422 the screen shows
while the person is still looking at the form, and in `handle_generate` it is the last
word, because the offered list is edited from the panel while jobs sit in the queue.
"""

import pytest
from fastapi import HTTPException

from server.routers import jobs
from variatio import config


@pytest.fixture(autouse=True)
def offered(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["el-rapido", "el-que-delibera"])


def test_a_commission_may_name_any_offered_model():
    jobs._check_params("generate", {"model": "el-que-delibera"})


def test_a_commission_that_names_none_is_the_normal_case():
    jobs._check_params("generate", {"n": 2})
    jobs._check_params("generate", {})


def test_a_model_nobody_offers_is_refused_with_the_list():
    with pytest.raises(HTTPException) as error:
        jobs._check_params("generate", {"model": "el-de-otra-instalacion"})
    assert error.value.status_code == 422
    assert "el-rapido" in error.value.detail


# Every other kind carries parameters of its own shape, and none of them names a writer.
def test_no_other_kind_is_asked_about_a_model():
    jobs._check_params("build_kg", {"model": "el-de-otra-instalacion"})
