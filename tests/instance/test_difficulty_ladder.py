"""Reading a difficulty back: which field carries it, and where an item sits on the ladder.

The writer resolves the canonical name from its own prompt set; a READER cannot, because
the name is the workspace's prompt language's and the bank listing that sorts a table has
no business looking that up. So both names are recognised here, and the rank comes from the
modality's own `enum` rather than from a table — a profile somebody renamed the rungs of by
hand still sorts the way its own declaration reads.
"""

import pytest

from variatio.instance.exemplars_profile import UNRANKED_DIFFICULTY, ExemplarsProfile


def _profile(tmp_path, name="nivel_dificultad", levels=("basico", "intermedio", "avanzado"), **extra):
    raw = {
        "item_types": {
            "escritura": {
                "primary_field": "enunciado",
                "fields": {
                    "enunciado": {"schema": {"type": "string"}},
                    **({name: {"schema": {"enum": list(levels)}, "decided_by": "user"}} if name else {}),
                },
            },
            **extra,
        }
    }
    path = tmp_path / "profile.json"
    import json

    path.write_text(json.dumps(raw), encoding="utf-8")
    return ExemplarsProfile(path)


@pytest.mark.parametrize("name", ["nivel_dificultad", "difficulty_level"])
def test_either_canonical_name_is_recognised(tmp_path, name):
    profile = _profile(tmp_path, name=name)
    assert profile.item_types["escritura"].difficulty_field == name


def test_a_modality_without_one_says_so_rather_than_guessing(tmp_path):
    item_type = _profile(tmp_path, name=None).item_types["escritura"]
    assert item_type.difficulty_field is None
    assert item_type.difficulty_levels == []
    assert item_type.difficulty_of({"enunciado": "x"}) is None
    assert item_type.difficulty_rank({"enunciado": "x"}) == UNRANKED_DIFFICULTY


def test_the_rank_is_the_position_in_the_modality_s_own_ladder(tmp_path):
    item_type = _profile(tmp_path, levels=("facil", "normal", "duro", "brutal")).item_types["escritura"]
    ranks = [item_type.difficulty_rank({"nivel_dificultad": v}) for v in ("facil", "normal", "duro", "brutal")]
    assert ranks == [0, 1, 2, 3]


def test_a_value_off_the_ladder_ranks_last_instead_of_passing_for_the_entry_level(tmp_path):
    # Sorting it to 0 would put an item nobody could classify at the top of "easiest first".
    item_type = _profile(tmp_path).item_types["escritura"]
    assert item_type.difficulty_rank({"nivel_dificultad": "imposible"}) == UNRANKED_DIFFICULTY
    assert item_type.difficulty_rank({"nivel_dificultad": ""}) == UNRANKED_DIFFICULTY
    assert item_type.difficulty_rank({}) == UNRANKED_DIFFICULTY


def test_the_profile_resolves_the_modality_before_ranking(tmp_path):
    second = {
        "primary_field": "pregunta",
        "fields": {
            "pregunta": {"schema": {"type": "string"}},
            "nivel_dificultad": {"schema": {"enum": ["basico", "intermedio", "avanzado"]}},
        },
    }
    profile = _profile(tmp_path, test=second)
    assert profile.difficulty_rank_of({"item_type": "test", "nivel_dificultad": "avanzado"}) == 2
    # An item the profile cannot place must not raise: the listing sorts over stale banks.
    assert profile.difficulty_rank_of({"item_type": "se_fue"}) == UNRANKED_DIFFICULTY
