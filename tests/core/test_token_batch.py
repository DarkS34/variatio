"""A stream's tokens leave in batches, at most one event every `TOKEN_BATCH_SECONDS`.

A model writes tens of tokens a second, and each one was an event of its own: on the bus,
in the job's record on disk and down every socket of the subject. The screen only ever
concatenates them, so gathering them changes what travels and not what is read.

What must not change: the first token leaves at once, reasoning and answer never share an
event, and nothing is lost at the end of an answer — cut short or not.
"""

import pytest

from variatio.core import inference, progress


class _Host:
    """An emitter that keeps every token event it is handed."""

    def __init__(self):
        self.tokens: list[tuple[str, str]] = []

    def emit(self, kind, payload):
        if kind == "token":
            self.tokens.append((payload["text"], payload["channel"]))

    def should_cancel(self) -> bool:
        return False


@pytest.fixture
def clock(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(progress.time, "monotonic", lambda: now[0])
    return now


def test_tokens_within_the_interval_leave_as_one_event(clock):
    host = _Host()
    with progress.emitting(host):
        sink = progress.token_sink("item")
        sink("Ho", "answer")
        clock[0] += 0.03
        sink("la", "answer")
        clock[0] += 0.03
        sink(" mun", "answer")
        clock[0] += 0.05
        sink("do", "answer")
        sink.flush()

    assert host.tokens == [("Ho", "answer"), ("la mundo", "answer")]


def test_the_first_token_leaves_at_once(clock):
    host = _Host()
    with progress.emitting(host):
        progress.token_sink("item")("Ya", "answer")

    assert host.tokens == [("Ya", "answer")]


def test_a_change_of_channel_sends_what_was_gathered_first(clock):
    host = _Host()
    with progress.emitting(host):
        sink = progress.token_sink("item")
        sink("pienso", "thinking")
        clock[0] += 0.01
        sink(" más", "thinking")
        clock[0] += 0.01
        sink("Respuesta", "answer")
        sink.flush()

    assert host.tokens == [("pienso", "thinking"), (" más", "thinking"), ("Respuesta", "answer")]


def test_nothing_is_gathered_when_nobody_listens():
    assert progress.token_sink("item") is None


class _Engine:
    """An engine that streams its tokens in one burst, faster than the interval."""

    def __init__(self, fail: bool = False):
        self.fail = fail

    def generate_stream(self, model, prompt, think=None, on_token=None, sampling=None):
        for token in ("uno", " dos", " tres"):
            on_token(token, "answer")
        if self.fail:
            raise progress.Cancelled("cancelled by the user")
        return inference.GenerationResponse(response="uno dos tres")


def test_the_end_of_an_answer_sends_what_is_held(clock, monkeypatch):
    monkeypatch.setattr(inference, "engine", lambda: _Engine())
    host = _Host()
    with progress.emitting(host):
        inference.generate_stream("m", "p", on_token=progress.token_sink("item"))

    assert "".join(text for text, _ in host.tokens) == "uno dos tres"
    assert len(host.tokens) == 2


def test_an_answer_cut_short_still_sends_what_was_written(clock, monkeypatch):
    monkeypatch.setattr(inference, "engine", lambda: _Engine(fail=True))
    host = _Host()
    with progress.emitting(host), pytest.raises(progress.Cancelled):
        inference.generate_stream("m", "p", on_token=progress.token_sink("item"))

    assert "".join(text for text, _ in host.tokens) == "uno dos tres"
