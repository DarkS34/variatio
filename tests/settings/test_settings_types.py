import pytest

from variatio.settings.types import Impact, Setting, SettingError, coerce


def make(kind, default, **kw):
    return Setting(
        key="grupo.ajuste",
        name="AJUSTE",
        kind=kind,
        default=default,
        group="Grupo",
        doc="Una razón medida.",
        impact=Impact.NONE,
        **kw,
    )


def test_int_from_a_string_is_parsed():
    assert coerce(make("int", 1), "42") == 42


def test_float_accepts_an_int():
    assert coerce(make("float", 0.0), 1) == 1.0


def test_bool_reads_the_spanish_affirmatives():
    setting = make("bool", False)
    for text in ("1", "true", "yes", "on", "sí", "si", "TRUE"):
        assert coerce(setting, text) is True
    for text in ("0", "false", "no", "off", ""):
        assert coerce(setting, text) is False


def test_list_of_strings_splits_a_comma_chain():
    assert coerce(make("list[str]", []), "gemini, groq ,,gemini") == ["gemini", "groq", "gemini"]


def test_list_of_strings_accepts_a_real_list():
    assert coerce(make("list[str]", []), ["a", "b"]) == ["a", "b"]


def test_dict_of_ints_coerces_its_values():
    assert coerce(make("dict[str,int]", {}), {"main": "8", "otro": 4}) == {"main": 8, "otro": 4}


def test_a_nullable_setting_accepts_none():
    assert coerce(make("str", None, nullable=True), None) is None


def test_a_non_nullable_setting_refuses_none():
    with pytest.raises(SettingError, match="AJUSTE"):
        coerce(make("str", "x"), None)


def test_a_value_outside_choices_is_refused_naming_the_setting():
    setting = make("str", "low", choices=("low", "high"))
    with pytest.raises(SettingError, match="AJUSTE"):
        coerce(setting, "max")


def test_a_value_under_the_minimum_is_refused():
    with pytest.raises(SettingError, match="AJUSTE"):
        coerce(make("float", 0.4, minimum=0.0, maximum=1.0), 1.5)


def test_an_unparseable_int_is_refused_and_says_so():
    with pytest.raises(SettingError, match="AJUSTE"):
        coerce(make("int", 1), "no soy un número")


def test_a_setting_is_frozen():
    setting = make("int", 1)
    with pytest.raises(Exception):
        setting.default = 2


def test_an_unknown_kind_is_refused_at_declaration():
    with pytest.raises(SettingError, match="AJUSTE"):
        make("complex", 1)


def test_a_setting_without_prose_is_refused_at_declaration():
    with pytest.raises(SettingError, match="AJUSTE"):
        Setting(
            key="grupo.ajuste",
            name="AJUSTE",
            kind="int",
            default=1,
            group="Grupo",
            doc="   ",
            impact=Impact.NONE,
        )


def test_a_bool_setting_never_coerces_to_a_string():
    assert coerce(make("bool", False), True) is True
    assert coerce(make("bool", True), False) is False


def test_a_string_setting_refuses_a_structure():
    with pytest.raises(SettingError, match="AJUSTE"):
        coerce(make("str", "x"), {"a": 1})
