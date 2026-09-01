"""The save answers the same shape as the read, because the client believes it.

`useSaveStageReview` puts the reply straight into the query cache as the form's new state
— deliberately, so the badge does not flicker through a refetch. The save used to answer
`{artifact, hash, mine}` while the read answered those plus `built` and `instrument`, and
`StageReview` renders NOTHING without an instrument: saving made the whole block vanish,
and a reload brought it back because the reload went through the read.

Pinned on the shapes rather than on the screen, because that is where the two can drift.
"""

import inspect

from study.api import stages

READ_KEYS = {"artifact", "built", "hash", "instrument", "mine"}


def test_the_payload_carries_everything_the_form_needs():
    payload = stages._payload("knowledge_graph", "abc123", None)
    assert set(payload) == READ_KEYS
    assert payload["built"] is True
    assert payload["instrument"] is not None
    assert payload["mine"] is None


def test_nothing_built_says_so_and_still_carries_the_questions():
    payload = stages._payload("knowledge_graph", None, None)
    assert payload["built"] is False
    assert payload["hash"] is None
    # The questions travel anyway: the screen needs them to say what it WILL ask.
    assert payload["instrument"] is not None


def test_both_routes_answer_through_the_one_builder():
    """A second literal dict in either is how the two shapes drift apart again."""
    for route in (stages.read, stages.write):
        body = inspect.getsource(route)
        assert "_payload(" in body, f"«{route.__name__}» no pasa por _payload"
        assert '"instrument"' not in body, f"«{route.__name__}» arma su propia respuesta"
