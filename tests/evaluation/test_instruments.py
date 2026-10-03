"""What each profile is asked, and the properties the arithmetic downstream depends on.

The wording is the instrument: rewording it changes what was measured. These tests pin the
two things that must hold whatever the words are — that both profiles answer on the SAME
ordinal shape, so `store` scores them with one function, and that the four rubric keys
never move, because renaming one strands every session already judged.
"""

import pytest

from server.db.models import EVALUATOR_PROFILES, STUDENT, TEACHER
from evaluation.api import instruments
from evaluation.api.store import RATING_SCALES


def test_every_declared_profile_has_both_instruments():
    for profile in EVALUATOR_PROFILES:
        assert profile in instruments.TRIAGE
        assert profile in instruments.RUBRIC


def test_the_two_profiles_share_the_ordinal_shape():
    # Same values in the same order, best first. This is what lets `triage_summary` fold
    # "yes" and "partly" together without a per-profile table.
    for profile in EVALUATOR_PROFILES:
        values = [option["value"] for option in instruments.TRIAGE[profile]["options"]]
        assert tuple(values) == instruments.TRIAGE_VALUES


def test_the_two_profiles_are_asked_different_questions():
    # The whole point of the profile: a student does not teach, so "¿la pondrías en clase?"
    # would get an answer of convenience rather than none.
    assert (
        instruments.TRIAGE[TEACHER]["question"] != instruments.TRIAGE[STUDENT]["question"]
    )


def test_the_rubric_keys_are_the_ones_the_store_scores():
    for profile in EVALUATOR_PROFILES:
        assert tuple(instruments.RUBRIC[profile]) == RATING_SCALES


def test_every_rubric_scale_carries_both_ends():
    for profile in EVALUATOR_PROFILES:
        for key, scale in instruments.RUBRIC[profile].items():
            assert len(scale["ends"]) == 2, f"{profile}.{key}"
            assert scale["label"] and scale["question"]


def test_complexity_is_the_only_scale_whose_target_is_the_middle():
    # A 5 in `complexity` is as wrong as a 1, and the panel has to say so on screen — the
    # rule used to live only in a comment next to the arithmetic, where the person doing
    # the scoring could not read it.
    assert instruments.RATING_TARGET == {"complexity": 3}


@pytest.mark.parametrize("profile", [None, "", "docente", "nonsense"])
def test_an_unknown_or_missing_profile_falls_back_to_the_teacher(profile):
    # An installation that predates the column has every account unset. It must not refuse
    # to draw the screen because a column is empty.
    assert instruments.resolve(profile) == TEACHER


def test_the_payload_carries_everything_the_screen_needs_to_word_itself():
    payload = instruments.for_profile(STUDENT)

    assert payload["profile"] == STUDENT
    assert payload["triage"]["question"] == instruments.TRIAGE[STUDENT]["question"]
    assert [scale["key"] for scale in payload["rubric"]] == list(RATING_SCALES)
    assert payload["decline"]["label"]


def test_the_rubric_payload_marks_the_middle_target_and_nothing_else():
    payload = instruments.for_profile(TEACHER)
    targets = {scale["key"]: scale["target"] for scale in payload["rubric"]}

    assert targets["complexity"] == 3
    assert all(value is None for key, value in targets.items() if key != "complexity")


def test_the_decline_is_worded_about_the_subject_and_not_the_person():
    # "I do not feel qualified" says something about them, and says it in the masculine, which
    # the installation has no way of knowing. It is also the wrong claim: what is being
    # reported is the match between this panel and these three items.
    assert "capacitado" not in instruments.DECLINE_LABEL
    assert "criterio" in instruments.DECLINE_LABEL
