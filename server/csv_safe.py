"""One defusing of spreadsheet formulas, shared by the two CSV exports.

A cell opening with `=`, `+`, `-`, `@` or a control character is a FORMULA to Excel and to
LibreOffice, not text — and both exports carry columns somebody else typed: the study's
`instructions`, `evaluator_note`, `rating_comment` and the two lists built from names, and
the engine's per-phase breakdown. `=cmd|'/c calc'!A1` in a note is a program that runs on
the administrator's machine the moment they open the study's raw data, planted by any
evaluator, students included. The apostrophe is the standard defusing: the spreadsheet
reads the rest of the cell as text and shows it.

Quoting is not an alternative: the CSV parser strips the quotes before the cell is typed,
so `"=cmd|…"` reaches the sheet as a formula all the same.

The number exemption is what keeps the cure from being the disease. `-3` opens with a
dangerous character and is not a formula, and quoting it is the regression this mitigation
is known for: a column of negative numbers that arrives as text and no longer adds up.

The two exports live in different packages — `study/api/store.py` and
`server/routers/admin_engine.py` — and the study already imports `server`, while the
reverse would close a cycle. So the one copy lives here, on the side both can reach.
"""

import re

_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r", "\n")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$")


def cell(value):
    if not isinstance(value, str) or not value.startswith(_FORMULA_LEAD):
        return value
    return value if _NUMBER.match(value) else f"'{value}"


def row(values: dict) -> dict:
    return {key: cell(entry) for key, entry in values.items()}
