import json

import pytest

from variatio.core.cerebras_budget import (
    Budget,
    BudgetExhausted,
    Limits,
    estimate_tokens,
)

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
