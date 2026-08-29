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
