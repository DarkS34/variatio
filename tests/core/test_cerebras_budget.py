import json

import pytest

from variatio.core.cerebras_budget import (
    Budget,
    BudgetExhausted,
    Limits,
    estimate_tokens,
)
from variatio.core.paths import PROJECT_ROOT

LIMITS = Limits(requests_minute=5, tokens_minute=30_000, requests_day=2_400, tokens_day=1_000_000)


class Clock:
    def __init__(self, now: float = 1_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def budget(tmp_path, clock, limits: Limits = LIMITS) -> Budget:
    return Budget(tmp_path / "budget.json", limits=lambda: limits, clock=clock)


def spend(b: Budget, clock: Clock, n: int, tokens: int = 100, phase: str = "kg_extract") -> None:
    for _ in range(n):
        b.record("gemma-4-31b", phase, prompt_tokens=tokens, completion_tokens=0, headers={})
        clock.now += 0.1


# THE MINUTE WINDOW: WAIT ------------------------------------------------------------------


def test_an_empty_window_never_waits(tmp_path):
    clock = Clock()
    assert budget(tmp_path, clock).delay("gemma-4-31b", 1_000) == 0.0


def test_the_fifth_request_of_a_minute_waits_for_the_first_to_age_out(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 5)

    # The oldest of the five landed at t=1000.0 and the clock has moved 0.5 s since.
    assert b.delay("gemma-4-31b", 100) == pytest.approx(59.5, abs=0.01)


def test_a_request_that_would_overrun_the_token_minute_waits(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 2, tokens=14_000)

    assert b.delay("gemma-4-31b", 100) == 0.0
    assert b.delay("gemma-4-31b", 5_000) > 0


def test_the_window_rolls(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 5)
    clock.now += 61

    assert b.delay("gemma-4-31b", 100) == 0.0


def test_each_model_has_its_own_bucket(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 5)

    assert b.delay("gemma-4-31b", 100) > 0
    assert b.delay("otro-modelo-31b", 100) == 0.0


# THE DAY WINDOW: REFUSE -------------------------------------------------------------------


def test_the_daily_request_budget_raises_instead_of_waiting(tmp_path):
    clock = Clock()
    limits = Limits(requests_minute=5, tokens_minute=30_000, requests_day=3, tokens_day=1_000_000)
    b = budget(tmp_path, clock, limits)
    spend(b, clock, 3)
    clock.now += 120

    with pytest.raises(BudgetExhausted):
        b.delay("gemma-4-31b", 100)


def test_the_daily_token_budget_raises_instead_of_waiting(tmp_path):
    clock = Clock()
    limits = Limits(requests_minute=5, tokens_minute=30_000, requests_day=2_400, tokens_day=1_000)
    b = budget(tmp_path, clock, limits)
    spend(b, clock, 2, tokens=400)
    clock.now += 120

    with pytest.raises(BudgetExhausted):
        b.delay("gemma-4-31b", 400)


def test_the_day_rolls_too(tmp_path):
    clock = Clock()
    limits = Limits(requests_minute=5, tokens_minute=30_000, requests_day=3, tokens_day=1_000_000)
    b = budget(tmp_path, clock, limits)
    spend(b, clock, 3)
    clock.now += 86_401

    assert b.delay("gemma-4-31b", 100) == 0.0


# WHAT THE HEADERS SAY ---------------------------------------------------------------------

# Measured 2026-08-26 against the real API: `remaining-requests-*` matches the account's
# effective budget exactly, while the token counters lag (a 74-token call moved the daily
# remaining by 6). So a header may only ever LOWER what we believe is left.


def test_a_header_lowers_what_is_left(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.record(
        "gemma-4-31b",
        "kg_extract",
        prompt_tokens=100,
        completion_tokens=0,
        headers={"x-ratelimit-remaining-requests-minute": "1"},
    )

    # Locally one of five is spent, but the server says one is left: the server wins.
    assert b.delay("gemma-4-31b", 100) == 0.0
    b.record("gemma-4-31b", "kg_extract", prompt_tokens=100, completion_tokens=0, headers={})
    assert b.delay("gemma-4-31b", 100) > 0


def test_a_header_never_raises_what_is_left(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 4)
    b.record(
        "gemma-4-31b",
        "kg_extract",
        prompt_tokens=100,
        completion_tokens=0,
        headers={"x-ratelimit-remaining-tokens-day": "999994"},
    )

    assert b.snapshot()["models"][0]["windows"]["day"]["tokens_used"] == 500


def test_a_stale_header_stops_counting_once_its_window_has_rolled(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.record(
        "gemma-4-31b",
        "kg_extract",
        prompt_tokens=100,
        completion_tokens=0,
        headers={"x-ratelimit-remaining-requests-minute": "0"},
    )
    assert b.delay("gemma-4-31b", 100) > 0

    clock.now += 61
    assert b.delay("gemma-4-31b", 100) == 0.0


# The configured ceiling is a ceiling, and this is the regression that gave the module its
# reason to exist a second time: `remaining-*` used to be trusted to RAISE it, so the very
# first answer lifted the account's declared 5 req/min to the catalogue's 499 and the
# throttle held nothing ever again — one measured installation ran 91 requests in a minute
# and 2.8 M tokens in a day against settings of 5 and 1 M.
def test_a_remaining_above_the_configured_ceiling_does_not_raise_the_ceiling(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.record(
        "gemma-4-31b",
        "kg_extract",
        prompt_tokens=100,
        completion_tokens=0,
        headers={"x-ratelimit-remaining-tokens-day": "8000000"},
    )

    assert b.snapshot()["models"][0]["windows"]["day"]["tokens_limit"] == LIMITS.tokens_day


def test_a_generous_remaining_does_not_stop_the_gate_from_closing(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    generous = {
        f"x-ratelimit-remaining-{kind}-{window}": "500000"
        for kind in ("requests", "tokens")
        for window in ("minute", "day")
    }
    for _ in range(LIMITS.requests_minute):
        b.record("gemma-4-31b", "kg_extract", prompt_tokens=10, completion_tokens=0, headers=generous)

    assert b.delay("gemma-4-31b", 10) > 0


# A ledger written before 2026-08-29 carries the ceilings the ratchet learned. They are dead
# state, and a reader who finds 499 in the file must not have to wonder which number is in
# force, so the first write drops them.
def test_a_ledger_carrying_a_learned_ceiling_forgets_it(tmp_path):
    clock = Clock()
    path = tmp_path / "budget.json"
    path.write_text(
        json.dumps(
            {
                "models": {"gemma-4-31b": {"calls": [], "seen": {}, "ceiling": {"requests-minute": 499}}},
                "inflight": None,
                "seq": 0,
            }
        ),
        encoding="utf-8",
    )
    b = Budget(path, limits=lambda: LIMITS, clock=clock)
    b.record("gemma-4-31b", "kg_extract", prompt_tokens=10, completion_tokens=0, headers={})

    assert "ceiling" not in json.loads(path.read_text(encoding="utf-8"))["models"]["gemma-4-31b"]
    assert b.snapshot()["models"][0]["windows"]["minute"]["requests_limit"] == LIMITS.requests_minute


# THE PER-PHASE BREAKDOWN ------------------------------------------------------------------


def test_the_breakdown_adds_up_by_phase(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 2, tokens=100, phase="kg_extract")
    spend(b, clock, 1, tokens=500, phase="kg_clean_merge")

    phases = {row["phase"]: row for row in b.snapshot()["models"][0]["phases"]}
    assert phases["kg_extract"]["requests"] == 2
    assert phases["kg_extract"]["tokens"] == 200
    assert phases["kg_clean_merge"]["requests"] == 1
    assert phases["kg_clean_merge"]["tokens"] == 500


def test_the_breakdown_counts_both_halves_of_a_call(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.record("gemma-4-31b", "variant_generation", prompt_tokens=800, completion_tokens=200, headers={})

    row = b.snapshot()["models"][0]["phases"][0]
    assert row["prompt_tokens"] == 800
    assert row["completion_tokens"] == 200
    assert row["tokens"] == 1_000


def test_a_call_nobody_attributed_still_counts(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.record("gemma-4-31b", None, prompt_tokens=100, completion_tokens=0, headers={})

    assert b.snapshot()["models"][0]["phases"][0]["phase"] == "sin fase"


def test_the_breakdown_is_ordered_by_what_costs_most(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 1, tokens=100, phase="cheap")
    spend(b, clock, 1, tokens=900, phase="dear")

    assert [row["phase"] for row in b.snapshot()["models"][0]["phases"]] == ["dear", "cheap"]


def test_a_call_older_than_a_day_leaves_the_breakdown(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    spend(b, clock, 1)
    clock.now += 86_401
    spend(b, clock, 1, phase="later")

    assert [row["phase"] for row in b.snapshot()["models"][0]["phases"]] == ["later"]


# THE LEDGER CROSSES PROCESSES -------------------------------------------------------------

# Builds run in `server.jobs.build_worker`, a subprocess, and they are precisely what
# empties the daily budget. An in-process counter would let a build spend a whole day's
# tokens without the API ever knowing.


def test_the_ledger_survives_a_new_instance(tmp_path):
    clock = Clock()
    spend(budget(tmp_path, clock), clock, 5)

    assert budget(tmp_path, clock).delay("gemma-4-31b", 100) > 0


def test_a_corrupt_ledger_is_not_a_broken_engine(tmp_path):
    (tmp_path / "budget.json").write_text("{ not json", encoding="utf-8")
    clock = Clock()

    assert budget(tmp_path, clock).delay("gemma-4-31b", 100) == 0.0


# THE CALL IN FLIGHT -----------------------------------------------------------------------


def test_the_call_in_flight_is_visible_and_then_gone(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)

    b.begin("gemma-4-31b", "kg_extract")
    flying = budget(tmp_path, clock).snapshot()["inflight"]
    assert flying["model"] == "gemma-4-31b"
    assert flying["phase"] == "kg_extract"
    assert flying["waiting_until"] is None

    b.finish()
    assert budget(tmp_path, clock).snapshot()["inflight"] is None


def test_waiting_for_the_budget_says_until_when(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)

    b.begin("gemma-4-31b", "kg_extract", waiting=12.0)
    assert budget(tmp_path, clock).snapshot()["inflight"]["waiting_until"] == clock.now + 12.0


def test_a_call_left_behind_by_a_dead_process_goes_stale(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.begin("gemma-4-31b", "kg_extract")
    clock.now += 3_600

    assert budget(tmp_path, clock).snapshot()["inflight"] is None


# THE PRE-FLIGHT ESTIMATE ------------------------------------------------------------------


def test_the_estimate_grows_with_the_prompt():
    assert estimate_tokens("") > 0
    assert estimate_tokens("x" * 4_000) > estimate_tokens("x" * 400)


# A CALL THAT CAN NEVER FIT ----------------------------------------------------------------
#
# Reachable in practice rather than hypothetically: gemma-4-31b takes a 131 072-token
# context while the free tier allows 30 000 tokens a minute, so one large KG prompt is
# simply outside this budget. Before the guard, `_relief` found no call to age out on an
# empty window, reported relief «now», and let the request through to a 429 it would repeat
# for ever.


def test_a_call_larger_than_the_whole_window_is_refused_at_once(tmp_path):
    clock = Clock()
    with pytest.raises(BudgetExhausted, match="no cabe"):
        budget(tmp_path, clock).delay("gemma-4-31b", 40_000)


def test_it_is_refused_even_with_the_window_completely_empty(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    assert b.delay("gemma-4-31b", 29_000) == 0.0

    with pytest.raises(BudgetExhausted, match="no cabe"):
        b.delay("gemma-4-31b", 30_001)


def test_the_message_names_the_window_that_cannot_hold_it(tmp_path):
    clock = Clock()
    limits = Limits(requests_minute=5, tokens_minute=30_000, requests_day=2_400, tokens_day=20_000)
    with pytest.raises(BudgetExhausted, match="por día"):
        budget(tmp_path, clock, limits).delay("gemma-4-31b", 25_000)


# BOOKING THE ROOM ---------------------------------------------------------------------------

# The whole reason the remote lane can hold more than one job. Checking and then calling is
# not a throttle when two callers can check at once: both read the same window and both
# spend it. `wait` books what it lets through, so the second caller sees a smaller window
# than the first even though no answer has come back yet.
def test_the_gate_books_the_room_it_lets_through(tmp_path):
    clock = Clock()
    tight = Limits(requests_minute=2, tokens_minute=30_000, requests_day=2_400, tokens_day=1_000_000)
    b = budget(tmp_path, clock, tight)

    b.wait("gemma-4-31b", 100)
    b.wait("gemma-4-31b", 100)

    # Nothing has been recorded yet: before the booking existed, this was 0.0 and a third
    # call went straight out on a minute that had already been spent twice over.
    assert b.delay("gemma-4-31b", 100) > 0


def test_a_booking_is_visible_to_another_reader_of_the_same_file(tmp_path):
    clock = Clock()
    tight = Limits(requests_minute=1, tokens_minute=30_000, requests_day=2_400, tokens_day=1_000_000)
    budget(tmp_path, clock, tight).wait("gemma-4-31b", 100)

    assert budget(tmp_path, clock, tight).delay("gemma-4-31b", 100) > 0


def test_recording_settles_the_booking_rather_than_charging_twice(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    claim = b.wait("gemma-4-31b", 5_000)

    b.record("gemma-4-31b", "kg_extract", 400, 100, {}, claim=claim)

    minute = b.snapshot()["models"][0]["windows"]["minute"]
    assert minute["requests_used"] == 1
    # The estimate was 5 000 and the call cost 500: what stands is the exact figure.
    assert minute["tokens_used"] == 500


def test_releasing_a_booking_gives_the_room_back(tmp_path):
    clock = Clock()
    tight = Limits(requests_minute=1, tokens_minute=30_000, requests_day=2_400, tokens_day=1_000_000)
    b = budget(tmp_path, clock, tight)
    claim = b.wait("gemma-4-31b", 100)
    assert b.delay("gemma-4-31b", 100) > 0

    b.release(claim)

    assert b.delay("gemma-4-31b", 100) == 0.0


def test_releasing_a_settled_booking_does_not_refund_it(tmp_path):
    clock = Clock()
    tight = Limits(requests_minute=1, tokens_minute=30_000, requests_day=2_400, tokens_day=1_000_000)
    b = budget(tmp_path, clock, tight)
    claim = b.wait("gemma-4-31b", 100)
    b.record("gemma-4-31b", "kg_extract", 90, 10, {}, claim=claim)

    b.release(claim)

    assert b.delay("gemma-4-31b", 100) > 0


# A process that dies mid-call never settles its booking, and charging the day for calls
# that never went out would empty the budget over nothing. Same clock as the flight list.
def test_a_booking_nobody_settles_stops_charging_once_it_goes_stale(tmp_path):
    clock = Clock()
    tight = Limits(requests_minute=1, tokens_minute=30_000, requests_day=2_400, tokens_day=1_000_000)
    b = budget(tmp_path, clock, tight)
    b.wait("gemma-4-31b", 100)
    assert b.delay("gemma-4-31b", 100) > 0

    clock.now += 3_600

    assert b.delay("gemma-4-31b", 100) == 0.0


def test_a_call_nobody_booked_is_still_recorded(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.record("gemma-4-31b", "kg_extract", 90, 10, {})

    assert b.snapshot()["models"][0]["windows"]["minute"]["requests_used"] == 1


# SEVERAL CALLS AT ONCE ----------------------------------------------------------------------


def test_several_calls_can_be_in_flight_at_once(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    first = b.begin("gemma-4-31b", "kg_extract")
    b.begin("gemma-4-31b", "kg_clean_merge")

    assert budget(tmp_path, clock).snapshot()["inflight_count"] == 2

    b.finish(first)
    assert budget(tmp_path, clock).snapshot()["inflight_count"] == 1


# The card draws one, and the one worth drawing is the call the throttle is holding back:
# «esperando presupuesto» is the state somebody can act on, and it is not always the oldest.
def test_the_call_being_held_is_the_one_the_card_is_shown(tmp_path):
    clock = Clock()
    b = budget(tmp_path, clock)
    b.begin("gemma-4-31b", "kg_extract")
    clock.now += 1
    b.begin("gemma-4-31b", "kg_clean_merge", waiting=30.0)

    flying = budget(tmp_path, clock).snapshot()["inflight"]
    assert flying["phase"] == "kg_clean_merge"
    assert flying["waiting_until"] == clock.now + 30.0


def test_a_ledger_written_before_the_lane_had_room_still_reads(tmp_path):
    path = tmp_path / "budget.json"
    path.write_text(
        json.dumps(
            {
                "models": {},
                # The old single-slot shape, from before two jobs could call at once.
                "inflight": {"model": "gemma-4-31b", "phase": "kg_extract", "since": 1_000.0},
                "seq": 3,
            }
        ),
        encoding="utf-8",
    )
    clock = Clock()

    snapshot = Budget(path, limits=lambda: LIMITS, clock=clock).snapshot()

    assert snapshot["inflight"] is None
    assert snapshot["inflight_count"] == 0


# TWO WRITERS AT ONCE ------------------------------------------------------------------------

# The ledger used to lean on the queue for this — one job at a time meant two processes never
# called at once — and that assumption went with the remote lane's capacity. Separate `Budget`
# objects on one file share no process lock, so what has to hold the count is the flock.
def test_two_ledgers_on_one_file_do_not_lose_each_others_calls(tmp_path):
    import threading

    path = tmp_path / "budget.json"
    writers = 4
    each = 15

    def spend() -> None:
        ledger = Budget(path, limits=lambda: LIMITS)
        for _ in range(each):
            ledger.record("gemma-4-31b", "kg_extract", 10, 5, {})

    threads = [threading.Thread(target=spend) for _ in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    calls = json.loads(path.read_text(encoding="utf-8"))["models"]["gemma-4-31b"]["calls"]
    assert len(calls) == writers * each
    # Every call carries a sequence number of its own; a lost update would repeat one.
    assert len({call["n"] for call in calls}) == writers * each


def test_two_processes_do_not_lose_each_others_calls(tmp_path):
    import subprocess
    import sys

    path = tmp_path / "budget.json"
    each = 12
    script = (
        "from variatio.core.cerebras_budget import Budget, Limits;"
        f"b = Budget({str(path)!r}, limits=lambda: Limits(5, 30000, 2400, 1000000));"
        f"[b.record('gemma-4-31b', 'kg_extract', 10, 5, {{}}) for _ in range({each})]"
    )
    workers = [
        subprocess.Popen([sys.executable, "-c", script], cwd=str(PROJECT_ROOT))
        for _ in range(3)
    ]
    for worker in workers:
        assert worker.wait(timeout=60) == 0

    calls = json.loads(path.read_text(encoding="utf-8"))["models"]["gemma-4-31b"]["calls"]
    assert len(calls) == 3 * each


# The wait is bounded from the FIRST attempt and not from each one. With one caller that is
# the same thing; with several, the room that comes free can be taken by somebody else every
# round, and a per-attempt bound would hold a call for ever in ninety-second instalments.
def test_the_wait_is_bounded_from_the_first_attempt(tmp_path, monkeypatch):
    import time as real_time

    from variatio.core import cerebras_budget

    monkeypatch.setattr(cerebras_budget.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cerebras_budget.config, "CEREBRAS_MAX_WAIT_SECONDS", 90, raising=False)

    class Ticking:
        """A clock that moves 10 s every time anybody reads it, and gives up eventually.

        The ceiling is not decoration: without the deadline `wait` loops for ever here, and
        a regression that HANGS the suite is worse than one that fails it.
        """

        def __init__(self) -> None:
            self.now = 1_000.0
            self.reads = 0

        def __call__(self) -> float:
            self.reads += 1
            assert self.reads < 200, "wait() nunca se rindió: la espera dejó de estar acotada"
            self.now += 10.0
            return self.now

    b = budget(tmp_path, Ticking())
    # Always a minute short, however long we hold: the room keeps going to somebody else.
    monkeypatch.setattr(b, "_compute", lambda *a, **k: 60.0)

    started = real_time.monotonic()
    with pytest.raises(BudgetExhausted) as raised:
        b.wait("gemma-4-31b", 100, "kg_extract")

    assert "no se libera a tiempo" in str(raised.value)
    # It gave up rather than going round again, and it did not really sleep to do it.
    assert real_time.monotonic() - started < 5.0
    # And it left no claim behind: the room it never got is not charged to anybody.
    assert budget(tmp_path, Clock()).snapshot()["inflight_count"] == 0
