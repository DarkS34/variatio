"""The tutor's settings: its stage after the study's, its lane drawn, its two prompt sets alike.

Its boundary — `variatio` names it only in the registry, and `import consumers.tutor` stays a
library — is `tests/consumers/test_consumers_boundary.py`'s, with every other function's.
"""

import inspect

from consumers.chat import settings as chat_settings
from consumers.tutor import prompts
from consumers.tutor import settings as tutor_settings
from variatio.settings.registry import BY_KEY, EXTRA_MODEL_KEYS, PIPELINE, STAGES


def test_the_tutor_comes_after_the_study_and_before_the_chat_and_its_lane_is_drawn():
    # The functions' stages come last, in the order of their doors; the chat's door is the
    # fourth (2026-10-15).
    assert STAGES[-2:] == (tutor_settings.STAGE, chat_settings.STAGE)
    assert PIPELINE[-2:] == (tutor_settings.LANE, chat_settings.LANE)
    assert set(EXTRA_MODEL_KEYS) == set(tutor_settings.MODEL_KEYS) | set(chat_settings.MODEL_KEYS)


def test_every_pipeline_setting_a_turn_reads_exists_and_carries_the_tutor_s_stage():
    for key in tutor_settings.READS:
        assert key in BY_KEY, key
        assert tutor_settings.STAGE in BY_KEY[key].stages, key


def test_both_prompt_sets_have_the_same_names_and_signatures():
    es, en = prompts.of("es"), prompts.of("en")
    public = lambda module: {  # noqa: E731
        name: inspect.signature(value) if callable(value) else type(value)
        for name, value in vars(module).items()
        if not name.startswith("_") and name not in ("json",)
    }
    assert public(es) == public(en)
    assert len(es.METHOD_RULES) == len(en.METHOD_RULES)


def test_every_tutor_switch_is_a_bool_with_its_effort_drawn_under_its_call():
    for phase in tutor_settings.LANE.phases:
        if phase.setting is None:
            assert phase.fixed is not None and phase.effort is None, phase.key
            continue
        switch, effort = BY_KEY[phase.setting], BY_KEY[phase.effort]
        assert switch.kind == "bool" and switch.scope == "engine" and not switch.name
        assert effort.choices == ("low", "medium", "high", "max") and effort.default == "low"
        assert switch.phase == effort.phase == phase.key
        assert BY_KEY[phase.model].phase == phase.key
