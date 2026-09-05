"""The arithmetic the memoria will quote, pinned against hand-computed values.

These are the numbers a tribunal reads, so every expectation here is one that can be
checked on paper rather than one produced by running the code and freezing whatever came
out. Where a closed form exists — the binomial's symmetric tail, chi-square with two
degrees of freedom — the test states it as an identity.
"""

import math

from evaluation.api import store


def _decided(choice_arm, position=1, triage=None, seconds=None, profile="teacher", **extra):
    """One decided session's header, with only the fields the aggregates actually read."""
    opened = 1000.0
    return {
        "id": extra.pop("id", "s"),
        "set_id": extra.pop("set_id", "s"),
        "created_at": opened,
        "chosen_at": opened + (seconds if seconds is not None else 60.0),
        "opened_at": opened,
        "seconds": seconds if seconds is not None else 60.0,
        "choice": position,
        "choice_arm": choice_arm,
        "triage_arm": triage or {},
        "evaluator_profile": profile,
        "arm_status": {},
        "arm_elapsed_ms": {},
        **extra,
    }


# BINOMIAL --------------------------------------------------------------------------------


def test_a_fair_split_between_three_arms_is_not_significant():
    # 5 of 15 is exactly the null: nothing could be less surprising, so p is 1.
    assert store.binomial_p(5, 15, 1 / 3) == 1.0


def test_a_clean_sweep_is_significant():
    # Every one of twelve going to the same arm: p is the two-sided version of (1/3)^12,
    # which is far below any threshold anybody would pre-register.
    p = store.binomial_p(12, 12, 1 / 3)
    assert p is not None and p < 0.001


def test_the_binomial_matches_the_hand_computed_upper_tail():
    # With p0 = 1/3 and n = 6, the outcomes at least as unlikely as 6-of-6 are exactly
    # {6}, because P(0) = (2/3)^6 is bigger than P(6) = (1/3)^6.
    assert store.binomial_p(6, 6, 1 / 3) == (1 / 3) ** 6


def test_no_decided_sessions_gives_no_p_value_rather_than_zero():
    assert store.binomial_p(0, 0, 1 / 3) is None


# WILSON ----------------------------------------------------------------------------------


def test_wilson_never_leaves_the_unit_interval_at_the_extremes():
    # The case the textbook normal interval gets visibly wrong, and the reason this is
    # Wilson: 5 of 5 must not produce an upper bound above 1 nor a lower bound of exactly 1.
    low, high = store.wilson(5, 5)
    assert 0.0 < low < 1.0
    assert high == 1.0


def test_wilson_is_centred_near_the_observed_share():
    low, high = store.wilson(50, 100)
    assert low < 0.5 < high
    assert abs((low + high) / 2 - 0.5) < 0.01


def test_wilson_narrows_as_the_sample_grows():
    small = store.wilson(5, 10)
    large = store.wilson(50, 100)
    assert (large[1] - large[0]) < (small[1] - small[0])


# POSITION BIAS ---------------------------------------------------------------------------


def test_a_flat_spread_over_positions_raises_no_alarm():
    rows = [_decided("system", position=(index % 3) + 1) for index in range(30)]
    result = store.position_bias(rows)
    assert result["counts"] == {1: 10, 2: 10, 3: 10}
    assert result["chi2"] == 0.0
    assert result["p"] == 1.0


def test_everybody_picking_the_first_card_is_caught():
    rows = [_decided("system", position=1) for _ in range(30)]
    result = store.position_bias(rows)
    # chi2 = 2n = 60 when every observation lands in one of three equal cells.
    assert result["chi2"] == 60.0
    assert result["p"] < 0.001


def test_the_chi_square_p_is_the_closed_form_for_two_degrees_of_freedom():
    rows = [_decided("system", position=1) for _ in range(12)] + [
        _decided("rag", position=2) for _ in range(6)
    ]
    result = store.position_bias(rows)
    assert result["p"] == round(math.exp(-result["chi2"] / 2), 5)


def test_sessions_with_no_preference_do_not_enter_the_position_count():
    rows = [_decided(None, position=None) for _ in range(4)]
    assert store.position_bias(rows) == {"n": 0, "counts": {1: 0, 2: 0, 3: 0}, "p": None}


# TRIAGE ----------------------------------------------------------------------------------


def test_the_triage_is_counted_per_arm_and_not_per_position():
    rows = [
        _decided("system", triage={"system": "yes", "rag": "no", "naive": "partly"}),
        _decided("system", triage={"system": "yes", "rag": "partly", "naive": "no"}),
    ]
    summary = store.triage_summary(rows)
    assert summary["system"]["counts"] == {"yes": 2, "partly": 0, "no": 0}
    assert summary["system"]["outright"] == 1.0
    # «Con retoques» still saves the teacher work, so it counts as usable; «no» does not.
    assert summary["naive"]["usable"] == 0.5


def test_an_arm_nobody_triaged_is_absent_rather_than_zero():
    rows = [_decided("system", triage={"system": "yes"})]
    summary = store.triage_summary(rows)
    assert "system" in summary
    assert "rag" not in summary


# DECLINES --------------------------------------------------------------------------------


def test_a_declined_session_is_not_a_vote_for_nobody():
    declined = {
        "id": "d",
        "set_id": "d",
        "created_at": 1.0,
        "declined_at": 2.0,
        "chosen_at": None,
        "choice_arm": None,
        "arm_status": {},
        "arm_elapsed_ms": {},
    }
    result = store.aggregates([declined, _decided("system")])

    assert result["declined"] == 1
    assert result["decided"] == 1
    # The one that matters: «no me veo capacitado» must not become a «ninguna me convence».
    assert result["preferences"]["none"] == 0
    assert result["preferences"]["system"] == 1


# DURATION --------------------------------------------------------------------------------


def test_the_duration_is_a_median_so_one_abandoned_tab_cannot_move_it():
    rows = [_decided("system", seconds=value) for value in (30, 40, 50, 60, 90_000)]
    duration = store._duration_summary(rows)
    assert duration["median"] == 50
    assert duration["slowest"] == 90_000


def test_sessions_decided_too_fast_are_counted_so_they_can_be_reported():
    rows = [_decided("system", seconds=value) for value in (5, 8, 45, 120)]
    assert store._duration_summary(rows)["under_20s"] == 2


# AGREEMENT -------------------------------------------------------------------------------


def _judged(set_id, account, arm, triage=None):
    row = _decided(arm, triage=triage)
    row.update({"id": f"{set_id}-{account}", "set_id": set_id, "account_id": account})
    return row


def test_two_evaluators_of_different_sets_are_not_a_pair():
    rows = [_judged("A", 1, "system"), _judged("B", 2, "system")]
    result = store.agreement(rows)
    assert result["sets_shared"] == 0
    assert result["choice"] == {"pairs": 0}


def test_two_evaluators_of_the_same_set_agreeing_gives_perfect_observed_agreement():
    rows = [_judged("A", 1, "system"), _judged("A", 2, "system")]
    result = store.agreement(rows)
    assert result["sets_shared"] == 1
    assert result["choice"]["pairs"] == 1
    assert result["choice"]["observed"] == 1.0
    # Everybody said the same thing every time, so there is no chance term to correct
    # against and kappa is undefined. Reported as null, never as a perfect 1.
    assert result["choice"]["kappa"] is None


def test_disagreement_produces_a_kappa_below_the_observed_agreement():
    rows = [
        _judged("A", 1, "system"),
        _judged("A", 2, "rag"),
        _judged("B", 1, "system"),
        _judged("B", 2, "system"),
    ]
    result = store.agreement(rows)
    assert result["choice"]["pairs"] == 2
    assert result["choice"]["observed"] == 0.5
    assert result["choice"]["kappa"] < result["choice"]["observed"]


def test_the_same_account_judging_a_set_twice_is_consistency_and_not_agreement():
    # Test-retest is a legitimate reliability measure and deliberately NOT pooled in here:
    # one person agreeing with themselves would flatter a number about a panel.
    rows = [_judged("A", 7, "system"), _judged("A", 7, "system")]
    assert store.agreement(rows)["choice"]["pairs"] == 0


def test_the_triage_contributes_three_pairs_per_shared_session():
    triage = {"system": "yes", "rag": "partly", "naive": "no"}
    rows = [_judged("A", 1, "system", triage), _judged("A", 2, "system", triage)]
    assert store.agreement(rows)["triage"]["pairs"] == 3


# GROUPING --------------------------------------------------------------------------------


def test_teachers_and_students_are_counted_apart():
    rows = [
        _judged("A", 1, "system") | {"evaluator_profile": "teacher"},
        _judged("B", 2, "rag") | {"evaluator_profile": "student"},
        _judged("C", 3, "system") | {"evaluator_profile": "student"},
    ]
    groups = {group["label"]: group for group in store.by_profile(rows)}
    assert groups["Alumnos"]["sessions"] == 2
    assert groups["Docentes"]["preferences"]["system"] == 1
    assert groups["Alumnos"]["preferences"]["system"] == 1


def test_an_account_with_no_profile_is_grouped_as_unset_rather_than_dropped():
    rows = [_judged("A", 1, "system") | {"evaluator_profile": None}]
    labels = [group["label"] for group in store.by_profile(rows)]
    assert labels == ["Sin perfil"]
