from server.routers.ws import COLD_REPLAY_LIMIT, trim_cold_replay


def event(seq, kind):
    return {"seq": seq, "kind": kind}


def test_a_cold_replay_carries_no_tokens():
    events = [event(1, "job.started"), event(2, "token"), event(3, "step.progress")]
    trimmed = trim_cold_replay(events)
    assert [e["kind"] for e in trimmed] == ["job.started", "step.progress"]


def test_the_cold_replay_is_bounded_and_keeps_the_newest():
    events = [event(i, "log") for i in range(COLD_REPLAY_LIMIT + 500)]
    trimmed = trim_cold_replay(events)
    assert len(trimmed) == COLD_REPLAY_LIMIT
    assert trimmed[-1]["seq"] == events[-1]["seq"]
    assert trimmed[0]["seq"] == events[500]["seq"]


def test_the_bound_applies_after_the_token_filter():
    events = [event(i, "token") for i in range(COLD_REPLAY_LIMIT)]
    events += [event(COLD_REPLAY_LIMIT + i, "step.progress") for i in range(10)]
    trimmed = trim_cold_replay(events)
    assert len(trimmed) == 10
    assert all(e["kind"] == "step.progress" for e in trimmed)
