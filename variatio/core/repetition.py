"""Telling an answer that has stopped saying anything new from one that is merely long.

A model copying a page can lock onto a drawn element — the empty cells of a grid, a
fill-in line, a border — and write it again and again until its output budget runs out.
Measured on the reference installation: a page of «| | | |» rows cut at the 4 096-token
cap three times over with the same 7 368 characters, and the page before it stopped on
its own after 271 identical rows and was cached as a page WITH content. The output cap
catches the first shape and nothing catches the second, which is why the detection lives
here, PURE, so the engine can ask it between two chunks and the page cache can ask it in
cold about a page already on disk.

Two shapes:
- a LINE loop: lines repeating with a short period — a grid row, a block of rows;
- a CHARACTER loop: a short unit repeated with no line break in it — `\\_`, a rule of
  dashes, a run of dots.

And two questions. `detect_tail` asks whether the text ENDS in a loop, which is what a
stream is asked every few hundred characters — cheap, and the loop is caught as it
happens. `detect` asks whether the text holds one ANYWHERE, which is what a cached page
is asked and what an answer that arrived whole is asked: the model that stops repeating
on its own goes on to close the fence and finish the page, so on a finished text the
loop is in the middle.
"""

import re
from dataclasses import dataclass

# How many trailing lines must repeat before a line loop is declared. A drawn grid is tens
# of identical rows; a real table repeats nothing this long, and a page of code written by
# a person does not carry twenty-four identical lines in a row.
LINE_LOOP_LINES = 24
# The longest block of lines that counts as one repeated unit. Above it the repetition is
# content — two identical stanzas are two stanzas.
MAX_LINE_PERIOD = 8
# At least this many repetitions of a block, whatever its length.
MIN_LINE_REPEATS = 4
# How many trailing characters must repeat a short unit before a character loop is declared:
# a rule of four hundred underscores is a drawing, not text, and a Markdown table separator
# or a heading underline never runs this long.
CHAR_LOOP_CHARS = 400
MAX_CHAR_PERIOD = 16

# How much of a repeated unit is quoted back — to the model on the retry, to a person on
# the failure marker. A grid row is thirty characters; the rest of a long unit says nothing.
QUOTE_CHARS = 60


@dataclass(frozen=True)
class Loop:
    """Where a repetition begins in a text, and what it repeats."""

    start: int
    unit: str


# A character loop anywhere: the shortest unit of up to `MAX_CHAR_PERIOD` characters that
# repeats at least this many times in a row; the match is then measured against
# `CHAR_LOOP_CHARS`. A lazy unit finds `\_` before `\_\_`, and the repeat floor keeps the
# search from stopping at every doubled letter of ordinary prose.
_CHAR_RUN_RE = re.compile(r"(.{1,%d}?)\1{24,}" % MAX_CHAR_PERIOD, re.DOTALL)


def detect(text: str) -> Loop | None:
    """Return the first loop found ANYWHERE in the text, or `None`.

    A line loop is looked for first because its unit — a whole line — is what a person
    or the retry prompt can be told about; a row of a grid also repeats as characters, and
    the character shape is what catches a run with no line break in it at all.
    """
    return _line_run(text) or _char_run(text)


def detect_tail(text: str) -> Loop | None:
    """Return the loop the text's TAIL is caught in, or `None` while it is still saying things."""
    return _line_loop(text) or _char_loop(text)


def cut(text: str, loop: Loop) -> str:
    """The text up to where the loop begins, with a code fence the cut left open closed.

    What comes before the loop is what the model read before it locked — a title, a
    paragraph, the first row that carried figures — and it is teaching material; the
    repeated rows are not.
    """
    head = text[: loop.start].rstrip()
    if head.count("```") % 2:
        head += "\n```"
    return head


def quoted(unit: str) -> str:
    """One line naming a repeated unit, short enough to sit inside a sentence."""
    flat = " ⏎ ".join(part for part in unit.split("\n")).strip()
    return flat if len(flat) <= QUOTE_CHARS else flat[:QUOTE_CHARS] + "…"


def _line_run(text: str) -> Loop | None:
    """The first run of lines, anywhere, that repeats a block of at most `MAX_LINE_PERIOD`."""
    raw = text.split("\n")
    lines = [line.rstrip() for line in raw]
    for period in range(1, MAX_LINE_PERIOD + 1):
        needed = max(LINE_LOOP_LINES - period, (MIN_LINE_REPEATS - 1) * period)
        run = 0
        for i in range(period, len(lines)):
            if lines[i] != lines[i - period]:
                run = 0
                continue
            run += 1
            if run < needed:
                continue
            first = i - run + 1 - period
            unit = lines[first : first + period]
            # A run of blank lines is not a loop; the run keeps counting, and the next
            # line that differs re-anchors it.
            if any(line.strip() for line in unit):
                start = sum(len(line) + 1 for line in raw[:first])
                return Loop(start, "\n".join(unit))
    return None


def _char_run(text: str) -> Loop | None:
    """The first run of characters, anywhere, that repeats a unit of at most `MAX_CHAR_PERIOD`."""
    for match in _CHAR_RUN_RE.finditer(text):
        unit = match.group(1)
        if unit.strip() and len(match.group(0)) >= CHAR_LOOP_CHARS + len(unit):
            return Loop(match.start(), unit)
    return None


def _line_loop(text: str) -> Loop | None:
    """A tail of `LINE_LOOP_LINES` lines that repeats a block of at most `MAX_LINE_PERIOD`."""
    raw = text.split("\n")
    lines = [line.rstrip() for line in raw]
    # A stream ends mid-line, so a last line with no newline after it may still be being
    # written and is not judged; a page ends in a newline, and that trailing blank is not
    # a line either. A loop is judged on the lines actually written whole.
    end = len(lines) - (0 if text.endswith("\n") else 1)
    while end > 0 and not lines[end - 1]:
        end -= 1
    lines = lines[:end]
    for period in range(1, MAX_LINE_PERIOD + 1):
        # Each compared line equals the one `period` earlier, so `needed` comparisons over
        # `needed + period` lines: twenty-four identical lines for a row, four blocks for a
        # block of eight.
        needed = max(LINE_LOOP_LINES - period, (MIN_LINE_REPEATS - 1) * period)
        if len(lines) < needed + period:
            break
        if not all(lines[-i] == lines[-i - period] for i in range(1, needed + 1)):
            continue
        if not any(line.strip() for line in lines[-period:]):
            continue
        k = len(lines) - 1
        while k - period >= 0 and lines[k] == lines[k - period]:
            k -= 1
        first = k - period + 1
        start = sum(len(line) + 1 for line in raw[:first])
        return Loop(start, "\n".join(lines[first : first + period]))
    return None


def _char_loop(text: str) -> Loop | None:
    """A tail of `CHAR_LOOP_CHARS` characters that repeats a unit of at most `MAX_CHAR_PERIOD`."""
    for period in range(1, MAX_CHAR_PERIOD + 1):
        if len(text) < CHAR_LOOP_CHARS + period:
            break
        if not all(text[-i] == text[-i - period] for i in range(1, CHAR_LOOP_CHARS + 1)):
            continue
        unit = text[-period:]
        if not unit.strip():
            continue
        k = len(text) - 1
        while k - period >= 0 and text[k] == text[k - period]:
            k -= 1
        return Loop(k - period + 1, unit)
    return None
