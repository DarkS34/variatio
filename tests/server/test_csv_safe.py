import csv
import io

import pytest

from server import csv_safe

PAYLOADS = [
    "=cmd|'/c calc'!A1",
    "+cmd|'/c calc'!A1",
    "-2+3+cmd|'/c calc'!A0",
    "@SUM(1+9)*cmd|'/c calc'!A0",
    "\t=1+1",
    "\r=1+1",
    "\n=1+1",
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_a_formula_never_leaves_the_export_as_one(payload):
    assert csv_safe.cell(payload).startswith("'")


# Quoting is not an alternative and this is why: the CSV reader strips the quotes before
# the spreadsheet decides what the cell is, so the payload would arrive as a formula all
# the same. The apostrophe survives that round trip and the `=` is no longer leading.
@pytest.mark.parametrize("payload", PAYLOADS)
def test_the_defusing_survives_a_csv_round_trip(payload):
    buffer = io.StringIO()
    csv.writer(buffer).writerow([csv_safe.cell(payload)])

    [[cell]] = csv.reader(io.StringIO(buffer.getvalue()))
    assert not cell.startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
    assert payload in cell


# The regression this mitigation is known for. A column of negative numbers quoted into
# text is a column the memoria cannot add up.
@pytest.mark.parametrize("number", ["-3", "-3.5", "-3,5", "+2", "-1e4", "0", "12"])
def test_a_number_is_left_exactly_as_it_was(number):
    assert csv_safe.cell(number) == number


def test_anything_that_is_not_a_string_is_left_alone():
    assert csv_safe.cell(7) == 7
    assert csv_safe.cell(None) is None
    assert csv_safe.cell("") == ""


def test_ordinary_text_is_untouched():
    assert csv_safe.cell("Recursividad · Memoización") == "Recursividad · Memoización"


def test_row_covers_every_column_it_is_given():
    assert csv_safe.row({"a": "=1+1", "b": "hola", "c": 3}) == {
        "a": "'=1+1",
        "b": "hola",
        "c": 3,
    }


# The engine's CSV is the one written for Excel on purpose — semicolons and a BOM — so it is
# the one where a formula would be opened by hand, by the administrator.
def test_the_engine_export_defuses_a_phase_name(tmp_path, monkeypatch):
    from server.routers import admin_engine
    from variatio import config
    from variatio.core import cerebras_budget

    cerebras_budget.use(tmp_path / "budget.json")
    monkeypatch.setattr(config, "CEREBRAS_MODELS", ["gemma-4-31b"])
    try:
        cerebras_budget.shared().record(
            "gemma-4-31b", "=cmd|'/c calc'!A1", prompt_tokens=10, completion_tokens=0, headers={}
        )
        body = admin_engine.cerebras_export().body.decode("utf-8")
    finally:
        cerebras_budget.use(None)

    [row] = list(csv.DictReader(io.StringIO(body.lstrip("﻿")), delimiter=";"))
    assert row["fase"] == "'=cmd|'/c calc'!A1"
