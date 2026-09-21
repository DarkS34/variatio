"""A model call in flight can be stopped, and abandoning it closes the connection.

Cancellation is cooperative — every per-item loop calls `progress.checkpoint()` between its
units — so with the answer arriving in one blocking read the smallest interruptible unit is
a whole model call, which on a contended GPU is minutes.

So `generate` streams INTERNALLY: nothing is emitted, the reassembled answer is what the
plain request returned, and the stop lands on the next token instead of the next call.
"""

import pytest

from variatio import config
from variatio.core import inference, progress
from variatio.core.inference import OllamaEngine


class _Chunk:
    """One streamed piece, shaped like the SDK's."""

    def __init__(
        self, response: str = "", thinking: str | None = None, done_reason: str | None = None
    ):
        self.response = response
        self.thinking = thinking
        self.done_reason = done_reason


class _Stream:
    """A stream that counts what was read and whether it was closed."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.read = 0
        self.closed = False

    def __iter__(self):
        for chunk in self._chunks:
            self.read += 1
            yield chunk

    def close(self):
        self.closed = True


class _Client:
    """Answers `generate` with a stream and records the request it was asked for."""

    def __init__(self, stream):
        self._stream = stream
        self.kwargs: dict = {}

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return self._stream

    def show(self, _model):
        raise AssertionError("las capacidades no se consultan en estas pruebas")


class _Emitter:
    """A host that asks to stop after `after` checkpoints."""

    def __init__(self, after: int | None):
        self._after = after
        self.seen = 0

    def emit(self, kind, payload):
        raise AssertionError(f"nada debe emitirse desde generate(): «{kind}»")

    def should_cancel(self) -> bool:
        self.seen += 1
        return self._after is not None and self.seen > self._after


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    monkeypatch.setattr(config, "LLM_CONTEXT", {})
    engine = OllamaEngine()
    # Both are asked of the model itself, and this test answers no HTTP.
    monkeypatch.setattr(type(engine), "supports_thinking", lambda self, m: True)
    monkeypatch.setattr(type(engine), "supports_vision", lambda self, m: True)
    return engine


def test_the_answer_is_streamed_and_reassembled_whole(engine):
    stream = _Stream([_Chunk("Hola, "), _Chunk("mundo"), _Chunk("."), _Chunk("")])
    engine._client = _Client(stream)

    answer = engine.generate(model="m", prompt="p")

    assert engine._client.kwargs["stream"] is True
    assert answer.response == "Hola, mundo."
    assert stream.closed


def test_the_sdks_reasoning_channel_survives_the_reassembly(engine):
    engine._client = _Client(
        _Stream([_Chunk("", "pien"), _Chunk("", "so"), _Chunk("respuesta")])
    )
    answer = engine.generate(model="m", prompt="p")
    assert answer.response == "respuesta"
    assert answer.thinking == "pienso"


def test_inline_think_tags_are_still_split_out(engine):
    engine._client = _Client(_Stream([_Chunk("<think>a</think>"), _Chunk("b")]))
    answer = engine.generate(model="m", prompt="p")
    assert answer.response == "b"
    assert answer.thinking == "a"


def test_a_cancellation_lands_on_the_next_chunk_not_the_next_call(engine):
    """The whole point: the stop takes effect DURING the answer, not after it."""
    stream = _Stream([_Chunk(str(i)) for i in range(100)])
    engine._client = _Client(stream)
    emitter = _Emitter(after=3)

    with progress.emitting(emitter):
        with pytest.raises(progress.Cancelled):
            engine.generate(model="m", prompt="p")

    assert stream.read == 4, "debería haber parado en el cuarto trozo, no al final"
    assert stream.closed, "la conexión ha de cerrarse para que el motor deje de generar"


def test_nothing_is_emitted_by_a_plain_generate(engine):
    """`_Emitter.emit` raises: a build's pipe must not carry one line per token."""
    engine._client = _Client(_Stream([_Chunk("a"), _Chunk("b")]))
    with progress.emitting(_Emitter(after=None)):
        assert engine.generate(model="m", prompt="p").response == "ab"


def test_a_grammar_and_the_reasoning_level_still_travel(engine):
    engine._client = _Client(_Stream([_Chunk("{}")]))
    engine.generate(model="m", prompt="p", think="low", format={"type": "object"})
    assert engine._client.kwargs["format"] == {"type": "object"}
    assert engine._client.kwargs["think"] == "low"


def test_a_failure_mid_stream_still_closes_it(engine):
    class _Broken(_Stream):
        def __iter__(self):
            yield _Chunk("a")
            raise RuntimeError("se cortó")

    stream = _Broken([])
    engine._client = _Client(stream)
    with pytest.raises(RuntimeError):
        engine.generate(model="m", prompt="p")
    assert stream.closed


def test_the_drain_survives_a_stream_that_cannot_be_closed():
    """A fake, a replay or a plain list has no `close`; that is not an error."""
    assert inference._drain(iter([_Chunk("a"), _Chunk("b")])) == ("ab", "", False, None)


# A REPETITION LOOP -------------------------------------------------------------------------------
#
# A model locked on a drawn grid writes the same row until its budget runs out. With
# `stop_on_loop` the read stops as soon as the tail is a repetition — the same abandonment
# as a cancellation — and the answer names what repeated.

ROW = "| | | |       | | | |\n"


def test_a_repetition_stops_the_read_and_names_what_repeated(engine):
    stream = _Stream([_Chunk("# Título\n")] + [_Chunk(ROW) for _ in range(400)])
    engine._client = _Client(stream)

    answer = engine.generate(model="m", prompt="p", stop_on_loop=True)

    assert answer.loop == ROW.rstrip("\n")
    assert stream.read < 200, "the read stopped inside the loop, not at its end"
    assert stream.closed, "the connection closes so the engine stops generating"
    assert answer.response.startswith("# Título")
    assert answer.truncated is False


def test_without_the_flag_a_repetition_is_read_whole(engine):
    stream = _Stream([_Chunk(ROW) for _ in range(100)])
    engine._client = _Client(stream)
    answer = engine.generate(model="m", prompt="p")
    assert answer.loop is None
    assert stream.read == 100


# THE OUTPUT CAP ----------------------------------------------------------------------------------
#
# A page whose header carries a fill-in line can be copied stroke for stroke for the
# engine's whole budget. Nothing in the TEXT says "this was cut"; the final chunk's
# `done_reason` does, and that is what the flag carries.


def test_the_output_cap_travels_as_num_predict_beside_the_context(engine, monkeypatch):
    monkeypatch.setattr(config, "LLM_CONTEXT", {"m": 8192})
    engine._client = _Client(_Stream([_Chunk("ok", done_reason="stop")]))
    engine.generate(model="m", prompt="p", temperature=0.0, max_output_tokens=4096)
    assert engine._client.kwargs["options"] == {
        "num_ctx": 8192,
        "temperature": 0.0,
        "num_predict": 4096,
    }


def test_no_cap_sends_no_num_predict(engine):
    engine._client = _Client(_Stream([_Chunk("ok")]))
    engine.generate(model="m", prompt="p")
    assert "num_predict" not in engine._client.kwargs.get("options", {})


def test_a_cut_answer_is_reported_as_truncated(engine):
    engine._client = _Client(
        _Stream([_Chunk("\\_\\_"), _Chunk("\\_\\_"), _Chunk("", done_reason="length")])
    )
    answer = engine.generate(model="m", prompt="p", max_output_tokens=4)
    assert answer.truncated is True
    assert answer.response == "\\_\\_\\_\\_", "lo leído se devuelve igualmente"


def test_a_finished_answer_is_not(engine):
    engine._client = _Client(_Stream([_Chunk("hola"), _Chunk("", done_reason="stop")]))
    assert engine.generate(model="m", prompt="p", max_output_tokens=4096).truncated is False
