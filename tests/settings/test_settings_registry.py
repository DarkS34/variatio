from variatio import config
from variatio.settings import derived
from variatio.settings.registry import BY_KEY, BY_NAME, GROUPS, REGISTRY

DERIVED_ONLY = {
    "EMBEDDING_MODELS",
    "TEMPERATURE_DEFAULT",
    "LLM_CONTEXT",
}

# An empty document prefix is qwen3-embedding's prescribed usage rather than an omission.
MAY_BE_EMPTY = {"EMBEDDING_DOCUMENT_PREFIX"}


def test_every_named_setting_is_an_attribute_of_config():
    for setting in REGISTRY:
        if not setting.name:
            continue
        assert hasattr(config, setting.name), f"config no expone {setting.name}"


def test_config_exposes_nothing_the_registry_does_not_declare():
    exposed = {
        name for name in config.__annotations__ if name.isupper() and not name.startswith("_")
    }
    accounted = set(BY_NAME) | set(derived.PHASES.values()) | DERIVED_ONLY
    assert exposed - accounted == set(), f"sin declarar: {exposed - accounted}"


def test_every_declared_name_is_annotated_in_config():
    annotated = set(config.__annotations__)
    declared = set(BY_NAME) | DERIVED_ONLY
    assert declared - annotated == set(), f"sin anotar en config.py: {declared - annotated}"


def test_every_annotated_name_actually_has_a_value():
    for name in config.__annotations__:
        if name in MAY_BE_EMPTY:
            continue
        assert getattr(config, name, None) is not None, f"{name} quedó sin valor"


def test_every_setting_carries_its_measured_prose():
    for setting in REGISTRY:
        assert len(setting.doc.strip()) >= 40, f"{setting.key} tiene la prosa vacía o truncada"


def test_no_setting_key_collides_with_another():
    keys = [setting.key for setting in REGISTRY]
    assert len(keys) == len(set(keys))
    assert len(BY_KEY) == len(REGISTRY)


def test_no_named_setting_collides_with_another():
    named = [setting.name for setting in REGISTRY if setting.name]
    assert len(named) == len(set(named))


def test_secrets_are_never_editable():
    for setting in REGISTRY:
        if setting.secret:
            assert not setting.editable, f"{setting.key} es secreto y editable"


def test_every_group_has_a_place_in_the_panel_order():
    extra = {setting.group for setting in REGISTRY} - set(GROUPS)
    assert not extra, f"grupos sin sitio en GROUPS: {extra}"


def test_every_phase_key_is_declared_in_the_registry():
    for key in derived.PHASES:
        assert key in BY_KEY, f"{key} lo deriva PHASES pero no lo declara nadie"


# 106 since the seventeen per-phase reasoning switches (89 when the generation checks got
# their retry budget, 88 when the admissibility judge became a phase of its own); the
# study's six are still declared outside this package and picked up by name. 97 named, not
# 111: the ten without one are the four context windows and the study's six, which the
# study reads through `study.config`, so none of them lands in `variatio.config`.
# The four SSH tunnel settings (2026-08-23) are all named. 112 since saved variants enter
# the prompt as already-used scenarios (GENERATION_AVOID_RECENT, 2026-08-23). 115 since
# the hybrid Cerebras engine (2026-08-24): base URL, API key and routing list, all named.
# 132 since each reasoning switch gained a per-phase effort (2026-08-24), seventeen unnamed
# `reasoning.effort.*` keys that only `derived` reads to resolve each `THINK_<FASE>`. 131
# later the same day: the global THINK_EFFORT left, replaced by those per-phase efforts —
# the boolean callers now map `True` to `inference.DEFAULT_THINK_EFFORT`. 134 since kg_units
# (2026-08-25), a phase of its own for segmenting the syllabus: a named model setting, a
# named reasoning switch and its unnamed per-phase effort. 139 since the Cerebras throttle
# (2026-08-26): the four measured ceilings of the account's rate limit — requests and tokens,
# per minute and per day — plus how long a call may wait for one to roll. All five named,
# and all five Impact.NONE, because the limiter reads them on every call: changing a ceiling
# has to take effect without resetting the engine or invalidating a single warm context.
# 144 since the corpus joined the page-transcription route (2026-08-27): the transcription
# phase was renamed `exemplars_transcribe` → `transcribe` because all three builders share
# it now, which moves no count, and the seam between two pages became a phase of its own —
# a named model, a named reasoning switch, its unnamed per-phase effort and how much of
# each page the judge is shown. The fifth is the bank builder's batch overlap, which is
# what makes the same seam survive the extractor's own cut.
def test_the_registry_holds_what_this_work_transcribed():
    # 141 since `models.main` and `context_window.main` were retired on 2026-08-28: with
    # every phase naming its own model there is nothing left for a main one to hand out,
    # and its context window went with it (the phases share `context_window.overrides`).
    # 143 before that, when `builders.kg_relation_schema` was retired: the relation
    # vocabulary follows a workspace's own `prompt_language` now.
    assert len(REGISTRY) == 141
    assert len(BY_NAME) == 113
