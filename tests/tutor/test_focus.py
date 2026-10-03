"""The focus belongs to the conversation: set once, moved only by a clearly different message."""

from tutor import focus

ELIGIBLE = {"Variable", "Función", "Recursividad", "Memoización"}


def step(current, scores, given=None):
    return focus.next_focus(
        current, scores, threshold=0.55, margin=0.05, eligible=ELIGIBLE, given=given
    )


def test_the_first_clear_message_sets_the_focus_and_a_vague_one_does_not():
    assert step([], {"Recursividad": 0.7, "Función": 0.5}) == ["Recursividad"]
    assert step([], {"Recursividad": 0.5}) == []


def test_two_concepts_neck_and_neck_both_enter():
    assert step([], {"Recursividad": 0.7, "Función": 0.68}) == ["Recursividad", "Función"]


def test_a_vague_message_keeps_the_focus_where_it_was():
    assert step(["Recursividad"], {"Variable": 0.5}) == ["Recursividad"]


def test_another_concept_has_to_beat_the_focus_by_the_margin_to_move_it():
    assert step(["Recursividad"], {"Función": 0.62, "Recursividad": 0.6}) == ["Recursividad"]
    assert step(["Recursividad"], {"Función": 0.8, "Recursividad": 0.6}) == ["Función"]


def test_concepts_the_turn_already_knows_win_outright_and_generic_ones_never_enter():
    assert step(["Variable"], {}, given=["Memoización", "Recursividad", "Función"]) == [
        "Memoización",
        "Recursividad",
    ]
    assert step([], {"Notación asintótica": 0.9}) == []


def test_a_message_about_what_comes_before_the_focus_never_moves_it():
    before = {"Función", "Variable"}
    moved = focus.next_focus(
        ["Recursividad"],
        {"Función": 0.8, "Recursividad": 0.6},
        threshold=0.55,
        margin=0.05,
        eligible=ELIGIBLE,
        before=before,
    )
    assert moved == ["Recursividad"]
    assert step(["Recursividad"], {"Memoización": 0.8, "Recursividad": 0.6}) == ["Memoización"]


def test_the_state_after_a_reply_is_the_focus_the_trail_and_the_maps_shown():
    state = {"focus": ["Variable"], "trail": ["Variable"], "verified": ["Función"]}

    after = focus.after_reply(state, ["Recursividad"])
    assert after == {"focus": ["Recursividad"], "trail": ["Variable", "Recursividad"], "mapped": []}

    drawn = focus.after_reply(after, ["Recursividad"], ["Recursividad"])
    assert drawn["mapped"] == ["Recursividad"] and drawn["since_map"] == 0
    assert focus.after_reply(drawn, ["Recursividad"])["since_map"] == 1


def test_a_chosen_concept_leads_and_the_message_s_own_may_join_it():
    chosen = lambda scores, before=None: focus.with_chosen(  # noqa: E731
        "Recursividad", scores, threshold=0.55, eligible=ELIGIBLE, before=before
    )

    assert chosen({"Variable": 0.3}) == ["Recursividad"]
    assert chosen({"Memoización": 0.7, "Recursividad": 0.9}) == ["Recursividad", "Memoización"]
    assert chosen({"Función": 0.8}, before={"Función", "Variable"}) == ["Recursividad"]
    assert chosen({"Notación asintótica": 0.9}) == ["Recursividad"], "a generic concept never joins"
