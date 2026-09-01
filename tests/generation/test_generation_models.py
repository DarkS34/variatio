"""Which model writes a variant: the installation offers, the commission chooses.

Two claims, and they are the ones every layer above depends on. A commission that names
nothing is written with the FIRST offered model — the same one `VARIANT_GENERATION_LLM`
resolves to, so the CLI and the study's three arms did not change when the screen gained
a chooser. And a name that is not on the list is refused rather than substituted: the
offered list is edited from the panel while jobs sit in the queue, so trusting what a
request carries would let a job run on a model the installation stopped offering.
"""

import pytest

from variatio import config, stages
from variatio.settings.registry import BY_KEY
from variatio.settings.types import SettingError, coerce


@pytest.fixture
def offered(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["el-rapido", "el-que-delibera"])
    return ["el-rapido", "el-que-delibera"]


def test_a_commission_that_names_nothing_gets_the_first_offered(offered):
    assert stages.resolve_generation_model(None) == "el-rapido"
    assert stages.resolve_generation_model("") == "el-rapido"


def test_a_commission_may_name_any_of_the_offered_models(offered):
    for model in offered:
        assert stages.resolve_generation_model(model) == model


def test_a_model_nobody_offers_is_refused_and_not_substituted(offered):
    with pytest.raises(stages.UnofferedModelError) as error:
        stages.resolve_generation_model("el-de-otra-instalacion")
    # The message names what IS offered: the screen shows it verbatim as a 422.
    assert "el-rapido" in str(error.value)


def test_the_offered_listing_is_a_copy_of_the_setting(offered):
    listing = stages.generation_models()
    assert listing == offered
    listing.append("intruso")
    assert stages.generation_models() == offered


# `settings.derived` indexes the list without a guard, so what keeps it from ever being
# empty is the declaration itself: emptying it from the panel or from the file is a
# validation error, and an invalid file value falls back to the registry's default.
def test_the_offered_list_may_not_be_emptied():
    setting = BY_KEY["generation.models"]
    assert coerce(setting, ["uno", "dos"]) == ["uno", "dos"]
    with pytest.raises(SettingError):
        coerce(setting, [])


# WHICH MODELS IGNORE THE REASONING LEVELS is a measurement, and since 2026-09-01 it is a
# setting rather than a table in the browser's source. It is deliberately NOT validated
# against the offered list: a model is taken off the offer far more often than its
# reasoning is re-measured, and dropping the measurement with it would force a re-run.
def test_the_fixed_effort_listing_is_a_copy_of_the_setting(monkeypatch):
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", ["el-rapido"])
    listing = stages.fixed_effort_models()
    assert listing == ["el-rapido"]
    listing.append("intruso")
    assert stages.fixed_effort_models() == ["el-rapido"]


def test_naming_a_model_nobody_offers_as_fixed_effort_is_not_an_error(offered, monkeypatch):
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", ["el-que-se-retiro-un-rato"])
    assert stages.fixed_effort_models() == ["el-que-se-retiro-un-rato"]
    # And it changes nothing about what may be generated with.
    assert stages.resolve_generation_model(None) == "el-rapido"


def test_the_two_lists_default_to_the_same_model_on_the_hybrid_engine():
    # Today's behaviour, moved out of `models.ts` unchanged: the one model measured to
    # answer the same at every level is the one the hybrid profile offers first.
    fixed = BY_KEY["generation.fixed_effort"]
    offered_setting = BY_KEY["generation.models"]
    assert fixed.default == []
    assert dict(fixed.engine_defaults or ()) == {"cerebras+ollama": ["gemma-4-31b"]}
    assert dict(offered_setting.engine_defaults or ())["cerebras+ollama"][0] == "gemma-4-31b"


def test_a_fixed_effort_value_reads_as_a_comma_list_or_is_refused():
    setting = BY_KEY["generation.fixed_effort"]
    # A string is split, which is what makes the environment override usable at all.
    assert coerce(setting, "gemma-4-31b, otro") == ["gemma-4-31b", "otro"]
    assert coerce(setting, []) == []
    with pytest.raises(SettingError):
        coerce(setting, {"gemma-4-31b": True})
