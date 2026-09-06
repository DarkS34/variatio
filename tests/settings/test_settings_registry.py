from variatio import config
from variatio.settings import derived
from variatio.settings.registry import BY_KEY, BY_NAME, GROUPS, REGISTRY

DERIVED_ONLY = {
    "EMBEDDING_MODELS",
    "TEMPERATURE_DEFAULT",
    "LLM_CONTEXT",
    # Not a setting: the commission picks its writer out of `generation.models`, and this is
    # the FIRST of them — what the CLI, the evaluation's arms and a request naming none are
    # written with.
    "VARIANT_GENERATION_LLM",
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


# The two counts are a tripwire, not a fact worth knowing: adding, removing or renaming a
# setting has to be a deliberate edit here. `REGISTRY` is every declaration, `BY_NAME` only
# those carrying a `name` and therefore becoming a `config` attribute — the four context
# windows, the per-phase reasoning efforts and the evaluation's own settings feed derived
# values and never land in `variatio.config`.
def test_the_registry_holds_what_this_work_transcribed():
    assert len(REGISTRY) == 150
    assert len(BY_NAME) == 118
