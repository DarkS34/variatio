"""Which model writes a variant: the installation offers, the commission chooses.

Two claims, and they are the ones every layer above depends on. A commission that names
nothing is written with the FIRST offered model — the same one `VARIANT_GENERATION_LLM`
resolves to, so the CLI did not change when the screen gained a chooser. And a name that is not on the list is refused rather than substituted: the
offered list is edited from the panel while jobs sit in the queue, so trusting what a
request carries would let a job run on a model the installation stopped offering.
"""

import pytest

from variatio import config, entrypoints
from variatio.settings.registry import BY_KEY
from variatio.settings.types import SettingError, coerce


@pytest.fixture
def offered(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["el-rapido", "el-que-delibera"])
    return ["el-rapido", "el-que-delibera"]


def test_a_commission_that_names_nothing_gets_the_first_offered(offered):
    assert entrypoints.resolve_generation_model(None) == "el-rapido"
    assert entrypoints.resolve_generation_model("") == "el-rapido"


def test_a_commission_may_name_any_of_the_offered_models(offered):
    for model in offered:
        assert entrypoints.resolve_generation_model(model) == model


def test_a_model_nobody_offers_is_refused_and_not_substituted(offered):
    with pytest.raises(entrypoints.UnofferedModelError) as error:
        entrypoints.resolve_generation_model("el-de-otra-instalacion")
    # The message names what IS offered: the screen shows it verbatim as a 422.
    assert "el-rapido" in str(error.value)


def test_the_offered_listing_is_a_copy_of_the_setting(offered):
    listing = entrypoints.generation_models()
    assert listing == offered
    listing.append("intruso")
    assert entrypoints.generation_models() == offered


# `settings.derived` indexes the list without a guard, so what keeps it from ever being
# empty is the declaration itself: emptying it from the panel or from the file is a
# validation error, and an invalid file value falls back to the registry's default.
def test_the_offered_list_may_not_be_emptied():
    setting = BY_KEY["generation.models"]
    assert coerce(setting, ["uno", "dos"]) == ["uno", "dos"]
    with pytest.raises(SettingError):
        coerce(setting, [])


# Which models IGNORE the reasoning levels is a measurement, and therefore a setting rather
# than a table in the browser's source. Deliberately NOT validated against the offered list:
# a model is taken off the offer far more often than its reasoning is re-measured, and
# dropping the measurement with it would force a re-run.
def test_the_fixed_effort_listing_is_a_copy_of_the_setting(monkeypatch):
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", ["el-rapido"])
    listing = entrypoints.fixed_effort_models()
    assert listing == ["el-rapido"]
    listing.append("intruso")
    assert entrypoints.fixed_effort_models() == ["el-rapido"]


def test_naming_a_model_nobody_offers_as_fixed_effort_is_not_an_error(offered, monkeypatch):
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", ["el-que-se-retiro-un-rato"])
    assert entrypoints.fixed_effort_models() == ["el-que-se-retiro-un-rato"]
    # And it changes nothing about what may be generated with.
    assert entrypoints.resolve_generation_model(None) == "el-rapido"


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


# With WHICH LEVEL a locked model is called is the other half of the same decision, and a
# setting too: locking says only that the requester does not choose, so without it the level
# is whatever the browser's slider happens to hold.
@pytest.fixture
def locked(monkeypatch):
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", ["el-rapido"])
    monkeypatch.setattr(config, "FIXED_EFFORT_LEVELS", {"el-rapido": "high"})


def test_a_locked_model_is_called_with_the_declared_level(locked):
    assert entrypoints.resolve_generation_effort("el-rapido", "low") == "high"
    assert entrypoints.resolve_generation_effort("el-rapido", True) == "high"


def test_resolving_the_effort_twice_says_the_same_thing(locked):
    once = entrypoints.resolve_generation_effort("el-rapido", "low")
    assert entrypoints.resolve_generation_effort("el-rapido", once) == once


def test_a_model_whose_effort_is_not_locked_keeps_what_arrived(locked):
    assert entrypoints.resolve_generation_effort("el-que-delibera", "max") == "max"
    assert entrypoints.resolve_generation_effort("el-que-delibera", True) is True


def test_a_locked_model_with_no_level_declared_is_left_to_the_engine(monkeypatch):
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", ["el-rapido"])
    monkeypatch.setattr(config, "FIXED_EFFORT_LEVELS", {})
    # `True`, and not a level this layer picked: `inference._think_option` is the one place
    # that turns it into `DEFAULT_THINK_EFFORT`, which is what the lock has always promised.
    assert entrypoints.resolve_generation_effort("el-rapido", "max") is True


def test_reasoning_switched_off_is_never_turned_back_on(locked):
    # The lock is about how much a model deliberates, never about whether it does.
    assert entrypoints.resolve_generation_effort("el-rapido", False) is False


def test_the_level_of_a_model_nobody_locked_is_kept_and_not_read(monkeypatch):
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", [])
    monkeypatch.setattr(config, "FIXED_EFFORT_LEVELS", {"el-rapido": "high"})
    assert entrypoints.fixed_effort_levels() == {"el-rapido": "high"}
    assert entrypoints.resolve_generation_effort("el-rapido", "low") == "low"


def test_a_level_outside_the_scale_is_refused_by_the_setting():
    setting = BY_KEY["generation.fixed_effort_levels"]
    assert coerce(setting, {"gemma-4-31b": "HIGH"}) == {"gemma-4-31b": "high"}
    assert coerce(setting, {}) == {}
    with pytest.raises(SettingError):
        coerce(setting, {"gemma-4-31b": "altísimo"})
    with pytest.raises(SettingError):
        coerce(setting, ["gemma-4-31b"])
