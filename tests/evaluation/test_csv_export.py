import csv
import io

from evaluation.api.store import export_csv


def _rows(body: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(body)))


def _session(**overrides) -> dict:
    row = {"id": "s1", "created_at": 1_700_000_000.0}
    row.update(overrides)
    return row


# A cell that opens with `=`, `+`, `-`, `@` or a control character is a FORMULA to Excel and
# to LibreOffice, not text. The columns below are free text an evaluator typed — a student
# included — and the file is opened by the administrator, so `=cmd|…!A1` in a note is a
# program that runs on somebody else's machine.
def test_a_formula_planted_in_a_note_arrives_as_text():
    body = export_csv([_session(evaluator_note="=cmd|' /c calc'!A1")])

    assert _rows(body)[0]["evaluator_note"] == "'=cmd|' /c calc'!A1"


def test_every_column_a_person_writes_into_is_defused():
    body = export_csv(
        [
            _session(
                instructions="=1+1",
                evaluator_note="@SUM(1)",
                concepts=["-2+3+cmd|' /c calc'!A0"],
                curriculum=["+1+1"],
                rating={"comment": "\t=1+1"},
            )
        ]
    )
    row = _rows(body)[0]

    assert row["instructions"] == "'=1+1"
    assert row["evaluator_note"] == "'@SUM(1)"
    assert row["concepts"] == "'-2+3+cmd|' /c calc'!A0"
    assert row["curriculum"] == "'+1+1"
    assert row["rating_comment"] == "'\t=1+1"


# The regression this mitigation is known for: quoting every cell that opens with a `-`
# turns a column of negative numbers into text that no longer adds up.
def test_a_negative_number_is_still_a_number():
    assert _rows(export_csv([_session(seconds=-3)]))[0]["seconds"] == "-3"
    assert _rows(export_csv([_session(seconds=-3.5)]))[0]["seconds"] == "-3.5"
    assert _rows(export_csv([_session(choice=0)]))[0]["choice"] == "0"


def test_ordinary_text_is_left_exactly_as_it_was():
    body = export_csv([_session(evaluator_note="El segundo enunciado es más claro.")])

    assert _rows(body)[0]["evaluator_note"] == "El segundo enunciado es más claro."
