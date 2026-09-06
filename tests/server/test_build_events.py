import json

import pytest

from server.jobs import build_process
from server.jobs.build_process import EVENT_KINDS, TERMINAL_KINDS, _dispatch


# The child merges its stderr into stdout, so anything a dependency prints — docling,
# pypdfium2, tqdm — travels down the same pipe as the protocol, and what those print can be
# text lifted straight out of a raw document somebody uploaded. Every event the parent acts
# on is therefore attacker-controllable unless the kind is checked first.
class _Control:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def emit(self, kind: str, payload: dict) -> None:
        self.events.append((kind, payload))


def _run(lines: list[dict]) -> tuple[_Control, dict, str | None]:
    control = _Control()
    result: dict = {"artifact": "knowledge_graph"}
    settled: set = set()
    failure: str | None = None
    for line in lines:
        failure = _dispatch(json.dumps(line), control, result, settled) or failure
    return control, result, failure


@pytest.mark.parametrize("kind", sorted(EVENT_KINDS))
def test_every_declared_kind_reaches_the_bus(kind):
    control, _, _ = _run([{"kind": kind, "id": "x"}])
    assert control.events == [(kind, {"id": "x"})]


# The forged ones are the point: `item.saved` puts a card in somebody's "Mis variantes"
# panel, `token` writes into the run drawer, and both are broadcast to every member of the
# workspace by a bus that never asked who wrote the line.
@pytest.mark.parametrize(
    "kind",
    ["item.saved", "item.produced", "item.rejected", "token", "prompt", "few_shot",
     "guardrail", "admissibility", "job.finished", "", "cualquier.cosa"],
)
def test_an_undeclared_kind_never_reaches_the_bus(kind):
    control, _, _ = _run([{"kind": kind, "id": "x"}])
    assert control.events == []


def test_a_kind_that_is_not_a_string_is_ignored():
    control, _, _ = _run([{"kind": 3}, {"kind": None}, {"kind": ["log"]}, {"nada": 1}])
    assert control.events == []


def test_a_line_that_is_not_a_json_object_is_ignored():
    control = _Control()
    settled: set = set()
    for payload in ["[1, 2]", '"log"', "null", "no es json", "3"]:
        assert _dispatch(payload, control, {}, settled) is None
    assert control.events == []


# ONE OUTCOME PER BUILD ---------------------------------------------------------------------


def test_the_first_result_is_the_one_that_counts():
    _, result, _ = _run(
        [
            {"kind": "worker.result", "artifact": "knowledge_graph", "size": 131},
            {"kind": "worker.result", "artifact": "falsificado", "size": 0},
        ]
    )
    assert result == {"artifact": "knowledge_graph", "size": 131}


def test_a_forged_result_after_a_failure_does_not_turn_it_into_a_success():
    _, result, failure = _run(
        [
            {"kind": "worker.failed", "error": "RuntimeError: se acabó"},
            {"kind": "worker.result", "artifact": "knowledge_graph", "size": 999},
        ]
    )
    assert failure == "RuntimeError: se acabó"
    assert "size" not in result


def test_a_forged_failure_after_a_result_does_not_break_the_build():
    _, result, failure = _run(
        [
            {"kind": "worker.result", "artifact": "knowledge_graph", "size": 131},
            {"kind": "worker.failed", "error": "inventado"},
        ]
    )
    assert failure is None
    assert result["size"] == 131


def test_a_result_carries_only_the_fields_the_worker_sends():
    _, result, _ = _run(
        [{"kind": "worker.result", "artifact": "kg", "size": 1, "approved": True}]
    )
    assert "approved" not in result


def test_a_cancellation_settles_the_build_too():
    _, result, _ = _run(
        [
            {"kind": "worker.cancelled"},
            {"kind": "worker.result", "artifact": "falsificado", "size": 7},
        ]
    )
    assert "size" not in result


def test_no_terminal_kind_ever_reaches_the_bus():
    control, _, _ = _run([{"kind": kind} for kind in sorted(TERMINAL_KINDS)])
    assert control.events == []


# The allowlist is a claim about what the worker emits, so it has to stay a subset of what
# the protocol knows about and must not quietly grow a generation event.
def test_the_two_lists_do_not_overlap():
    assert not (EVENT_KINDS & TERMINAL_KINDS)
    assert build_process.RESULT_FIELDS <= {"artifact", "size"}
