import csv
import io

from study.api import store

PAYLOAD = "=cmd|'/c calc'!A1"

# The columns an evaluator writes, directly or by picking names. A student can plant a
# formula in any of them, and the file it lands in is the study's raw data — opened by the
# administrator, in a spreadsheet, by hand.
WRITTEN_BY_THE_EVALUATOR = ("instructions", "evaluator_note", "rating_comment")


def _row(**extra) -> dict:
    return {
        "id": "abc123",
        "created_at": 1_700_000_000,
        "workspace": "aula",
        "account": "ana",
        "shuffle": ["naive", "rag", "system"],
        **extra,
    }


def _exported(row: dict) -> dict:
    [line] = list(csv.DictReader(io.StringIO(store.export_csv([row]))))
    return line


def test_the_free_text_columns_are_defused():
    line = _exported(
        _row(
            instructions=PAYLOAD,
            evaluator_note=PAYLOAD,
            rating={"comment": PAYLOAD, "arm": "system"},
        )
    )

    for column in WRITTEN_BY_THE_EVALUATOR:
        assert line[column] == f"'{PAYLOAD}"


def test_the_lists_built_from_names_are_defused():
    line = _exported(_row(concepts=[PAYLOAD, "Recursividad"], curriculum=[PAYLOAD]))

    assert line["concepts"].startswith("'=")
    assert line["curriculum"].startswith("'=")


def test_the_columns_the_analysis_reads_as_numbers_are_untouched():
    line = _exported(_row(seed=-4, think=True, seconds=-1, instructions="hola"))

    assert line["seed"] == "-4"
    assert line["seconds"] == "-1"
    assert line["think"] == "1"
    assert line["instructions"] == "hola"
