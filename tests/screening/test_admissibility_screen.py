import json

from variatio.runtime import screening
from variatio.runtime.screening import admissibility

from ..conftest import ES


class _Reply:
    def __init__(self, response):
        self.response = response


def _fake_generate(payload):
    def generate(**kwargs):
        if isinstance(payload, Exception):
            raise payload
        return _Reply(payload)

    return generate


def test_screen_returns_an_empty_ruling_without_calling_anyone(owners_for, monkeypatch):
    def explode(**kwargs):
        raise AssertionError("no debería llamar al modelo")

    monkeypatch.setattr(admissibility.inference, "generate", explode)
    ruling = screening.screen("   ", owners_for(), ["Recursividad"], ES)
    assert ruling.requests == ()
    assert ruling.ok


def test_screen_accepts_two_slots(owners_for, monkeypatch):
    payload = json.dumps(
        {
            "requests": [
                {"text": "que vaya de una panadería", "slot": "ambito", "owner": None, "term": None},
                {"text": "que sea breve", "slot": "extension", "owner": None, "term": None},
            ]
        }
    )
    monkeypatch.setattr(admissibility.inference, "generate", _fake_generate(payload))
    ruling = screening.screen("x", owners_for(), ["Recursividad"], ES)
    assert ruling.ok
    assert ruling.checked
    assert [r.slot for r in ruling.requests] == ["ambito", "extension"]


def test_screen_blocks_on_an_owner(owners_for, monkeypatch):
    payload = json.dumps(
        {
            "requests": [
                {"text": "que practique variables", "slot": None, "owner": "concepts", "term": "Variable"},
            ]
        }
    )
    monkeypatch.setattr(admissibility.inference, "generate", _fake_generate(payload))
    ruling = screening.screen("x", owners_for(), ["Recursividad"], ES)
    assert not ruling.ok
    assert ruling.blocked[0].owner.key == "concepts"
    assert ruling.blocked[0].term == "Variable"


def test_screen_fails_open_when_the_answer_is_unreadable(owners_for, monkeypatch):
    monkeypatch.setattr(admissibility.inference, "generate", _fake_generate("no soy json"))
    ruling = screening.screen("x", owners_for(), ["Recursividad"], ES)
    assert ruling.ok
    assert not ruling.checked
    assert ruling.requests == ()


def test_screen_fails_open_when_every_entry_is_discarded(owners_for, monkeypatch):
    payload = json.dumps(
        {
            "requests": [
                {"text": "x", "slot": None, "owner": "concepts", "term": "Punteros"},
            ]
        }
    )
    monkeypatch.setattr(admissibility.inference, "generate", _fake_generate(payload))
    ruling = screening.screen("x", owners_for(), ["Recursividad"], ES)
    assert ruling.ok
    assert not ruling.checked


def test_screen_fails_open_when_the_engine_raises(owners_for, monkeypatch):
    from variatio.core.inference import InferenceError

    monkeypatch.setattr(
        admissibility.inference, "generate", _fake_generate(InferenceError("motor caído"))
    )
    ruling = screening.screen("x", owners_for(), ["Recursividad"], ES)
    assert ruling.ok
    assert not ruling.checked
