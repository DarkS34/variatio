"""One defusing of spreadsheet formulas, shared by the two CSV exports.

Excel and LibreOffice read a cell opening with `=`, `+`, `-`, `@` or a control character
as a FORMULA, and both exports carry columns somebody else typed. A leading apostrophe is
the standard defusing; quoting is not an alternative, because the CSV parser strips the
quotes before the cell is typed. Numbers are exempt so a column of negative figures does
not arrive as text and stop adding up.

The copy lives here rather than in either caller because the study already imports
`server` and the reverse would close a cycle.
"""

import re

_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r", "\n")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$")


def cell(value):
    """Prefix an apostrophe to a value a spreadsheet would read as a formula."""
    if not isinstance(value, str) or not value.startswith(_FORMULA_LEAD):
        return value
    return value if _NUMBER.match(value) else f"'{value}"


def row(values: dict) -> dict:
    """Defuse every cell of one export row."""
    return {key: cell(entry) for key, entry in values.items()}
