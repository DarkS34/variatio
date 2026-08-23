from variant_generator import config, settings
from variant_generator.settings import derived
from variant_generator.settings.registry import BY_KEY, PIPELINE
from variant_generator.settings.registry import reasoning

PHASES = [phase for lane in PIPELINE for phase in lane.phases]


def test_every_phase_appears_once():
    keys = [phase.key for phase in PHASES]
    assert len(keys) == len(set(keys))


def test_every_phase_either_toggles_or_says_why_not():
    for phase in PHASES:
        assert (phase.setting is None) != (phase.fixed is None), phase.key
        if phase.fixed is not None:
            assert phase.fixed in {reasoning.GRAMMAR, reasoning.COMMISSION, reasoning.MODEL}


def test_every_toggle_is_a_bool_setting_of_the_reasoning_group():
    for phase in PHASES:
        if phase.setting is None:
            continue
        setting = BY_KEY[phase.setting]
        assert setting.kind == "bool"
        assert setting.group == reasoning.GROUP
        assert setting.name == f"THINK_{phase.key.upper()}"
        assert hasattr(config, setting.name)


def test_every_reasoning_switch_has_a_place_in_the_pipeline():
    declared = {s.key for s in reasoning.SETTINGS}
    drawn = {phase.setting for phase in PHASES if phase.setting}
    assert declared == drawn


def test_every_phase_names_a_model_the_registry_declares():
    for phase in PHASES:
        assert phase.model in BY_KEY, phase.key
        if phase.model.startswith("models.phases."):
            assert phase.model in derived.PHASES


def test_only_the_three_documented_exceptions_are_fixed():
    fixed = {phase.key: phase.fixed for phase in PHASES if phase.fixed}
    assert fixed == {
        "guardrail": reasoning.MODEL,
        "variant_generation": reasoning.COMMISSION,
        "repair": reasoning.GRAMMAR,
    }


def test_the_defaults_keep_what_each_call_did_before_the_switch_existed():
    on = {key for key, (default, _) in reasoning._DEFAULTS.items() if default}
    assert on == {
        "ep_consolidate",
        "kg_clean_merge",
        "kg_clean_drop",
        "kg_link_domain",
        "kg_link_cross_domain",
        "kg_taggable",
        "concept_tagger",
    }


def test_every_model_phase_is_drawn_in_the_pipeline():
    drawn = {phase.model for phase in PHASES}
    assert set(derived.PHASES) <= drawn


def test_the_serialised_pipeline_carries_the_same_shape():
    lanes = settings.pipeline()
    assert [lane["key"] for lane in lanes] == [lane.key for lane in PIPELINE]
    for lane in lanes:
        for phase in lane["phases"]:
            assert set(phase) == {"key", "label", "model", "setting", "fixed", "note"}
