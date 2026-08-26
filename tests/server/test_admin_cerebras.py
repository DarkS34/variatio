import csv
import io

import pytest

from server.routers import admin_engine
from variant_generator import config
from variant_generator.core import cerebras_budget


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    cerebras_budget.use(tmp_path / "budget.json")
    monkeypatch.setattr(config, "CEREBRAS_MODELS", ["gemma-4-31b"])
    monkeypatch.setattr(config, "CEREBRAS_API_KEY", "sk-de-mentira")
    monkeypatch.setattr(config, "CEREBRAS_MAX_WAIT_SECONDS", 90)
    book = cerebras_budget.shared()
    yield book
    cerebras_budget.use(None)


# WHAT THE PANEL POLLS ---------------------------------------------------------------------


def test_the_state_separates_what_is_routed_from_what_was_spent(ledger):
    ledger.record("gemma-4-31b", "kg_extract", prompt_tokens=800, completion_tokens=120, headers={})

    state = admin_engine.cerebras_state()
    assert state["routed"] == ["gemma-4-31b"]
    assert [entry["model"] for entry in state["usage"]] == ["gemma-4-31b"]


# The two keys used to be one, and the `**budget` spread silently overwrote the routed list
# with the usage list — a model routed but never called disappeared from the screen.
def test_a_routed_model_that_has_never_been_called_still_shows(ledger):
    state = admin_engine.cerebras_state()
    assert state["routed"] == ["gemma-4-31b"]
    assert state["usage"] == []


def test_a_model_called_after_leaving_the_routing_list_keeps_its_history(ledger, monkeypatch):
    ledger.record("gpt-oss-120b", "kg_clean_merge", prompt_tokens=500, completion_tokens=0, headers={})
    monkeypatch.setattr(config, "CEREBRAS_MODELS", ["gemma-4-31b"])

    state = admin_engine.cerebras_state()
    assert state["routed"] == ["gemma-4-31b"]
    assert [entry["model"] for entry in state["usage"]] == ["gpt-oss-120b"]


def test_the_key_is_reported_as_present_and_never_returned(ledger):
    state = admin_engine.cerebras_state()
    assert state["configured"] is True
    assert "sk-de-mentira" not in repr(state)


def test_the_state_carries_the_call_in_flight(ledger):
    ledger.begin("gemma-4-31b", "kg_extract")
    assert admin_engine.cerebras_state()["inflight"]["model"] == "gemma-4-31b"

    ledger.finish()
    assert admin_engine.cerebras_state()["inflight"] is None


# THE SPREADSHEET --------------------------------------------------------------------------


def _rows(body: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(body.lstrip("﻿")), delimiter=";"))


def test_the_export_carries_one_row_per_phase(ledger):
    ledger.record("gemma-4-31b", "kg_extract", prompt_tokens=800, completion_tokens=200, headers={})
    ledger.record("gemma-4-31b", "kg_extract", prompt_tokens=600, completion_tokens=100, headers={})
    ledger.record("gemma-4-31b", "kg_domains", prompt_tokens=300, completion_tokens=0, headers={})

    rows = _rows(admin_engine.cerebras_export().body.decode("utf-8"))
    by_phase = {row["fase"]: row for row in rows}
    assert by_phase["kg_extract"]["peticiones"] == "2"
    assert by_phase["kg_extract"]["tokens"] == "1700"
    assert by_phase["kg_extract"]["tokens_entrada"] == "1400"
    assert by_phase["kg_extract"]["tokens_salida"] == "300"
    assert by_phase["kg_domains"]["tokens"] == "300"


# Excel in a Spanish locale splits on `;` and needs the BOM to read the accents; the study's
# own export uses plain commas because nobody opens that one by hand.
def test_the_export_opens_in_a_spanish_excel(ledger):
    ledger.record("gemma-4-31b", None, prompt_tokens=100, completion_tokens=0, headers={})
    body = admin_engine.cerebras_export().body.decode("utf-8")

    assert body.startswith("﻿")
    assert body.splitlines()[0].count(";") == 6
    assert "sin fase" in body


def test_the_daily_share_is_written_with_a_decimal_comma(ledger, monkeypatch):
    monkeypatch.setattr(config, "CEREBRAS_MAX_TOKENS_DAY", 1_000_000)
    ledger.record("gemma-4-31b", "kg_extract", prompt_tokens=250_000, completion_tokens=0, headers={})

    assert _rows(admin_engine.cerebras_export().body.decode("utf-8"))[0]["porcentaje_del_dia"] == "25,00"


def test_an_empty_ledger_exports_a_header_and_nothing_else(ledger):
    body = admin_engine.cerebras_export().body.decode("utf-8")
    assert _rows(body) == []
    assert "modelo;fase" in body
