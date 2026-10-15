"""What a piece of work's model calls cost is counted by phase, on every meter open around it."""

from types import SimpleNamespace

from variatio.core import inference, progress, usage


def test_a_call_counts_on_every_open_meter_under_its_phase(monkeypatch):
    monkeypatch.setattr(progress, "current_activity", lambda: "tutor_reply")
    with usage.metering() as job:
        usage.record("ollama", "qwen", 100, 20)
        with usage.metering() as turn:
            usage.record("cerebras", "llama", 50, 5)
    usage.record("ollama", "qwen", 7, 7)  # no meter open: nothing counts

    assert job.summary() == {
        "calls": 2,
        "in": 150,
        "out": 25,
        "phases": [
            {"phase": "tutor_reply", "engine": "ollama", "model": "qwen", "calls": 1, "in": 100, "out": 20},
            {"phase": "tutor_reply", "engine": "cerebras", "model": "llama", "calls": 1, "in": 50, "out": 5},
        ],
    }
    assert turn.summary()["in"] == 50


def test_ollama_s_last_chunk_says_what_the_call_cost():
    chunks = [
        SimpleNamespace(response="ho", thinking=None),
        SimpleNamespace(response="la", thinking=None, done_reason="stop", prompt_eval_count=12, eval_count=3),
    ]

    *_, counts = inference._drain(iter(chunks))

    assert counts == (12, 3)


def test_a_summary_from_another_process_keeps_only_well_formed_rows():
    meter = usage.Meter()
    meter.merge({"phases": [{"phase": "kg_extract", "engine": "ollama", "model": "m", "calls": 2, "in": 10, "out": 4}, "x", {"calls": "many"}]})

    assert meter.summary()["calls"] == 2 and meter.summary()["in"] == 10
    assert usage.clean(None) == {"calls": 0, "in": 0, "out": 0, "phases": []}
