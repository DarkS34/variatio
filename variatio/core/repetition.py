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
from functools import lru_cache

from .. import config

# Every threshold is a setting (`builders.transcribe_loop_*`), read at each call: the
# detector also judges pages already on disk, so its verdict follows the value in force.

@dataclass(frozen=True)
class Loop:
    """Where a repetition begins in a text, and what it repeats."""

    start: int
    unit: str


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
    cap = config.TRANSCRIBE_LOOP_QUOTE_CHARS
    return flat if len(flat) <= cap else flat[:cap] + "…"


def _line_run(text: str) -> Loop | None:
    """The first run of lines, anywhere, that repeats a block of a few lines at most."""
    raw = text.split("\n")
    lines = [line.rstrip() for line in raw]
    for period in range(1, config.TRANSCRIBE_LOOP_MAX_LINE_PERIOD + 1):
        needed = max(
            config.TRANSCRIBE_LOOP_LINES - period,
            (config.TRANSCRIBE_LOOP_MIN_LINE_REPEATS - 1) * period,
        )
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
    """The first run of characters, anywhere, that repeats a short unit."""
    for match in _char_run_re(
        config.TRANSCRIBE_LOOP_MAX_CHAR_PERIOD, config.TRANSCRIBE_LOOP_CHAR_RUN_REPEATS
    ).finditer(text):
        unit = match.group(1)
        if unit.strip() and len(match.group(0)) >= config.TRANSCRIBE_LOOP_CHARS + len(unit):
            return Loop(match.start(), unit)
    return None


def _line_loop(text: str) -> Loop | None:
    """A tail of `TRANSCRIBE_LOOP_LINES` lines that repeats a block of a few lines at most."""
    raw = text.split("\n")
    lines = [line.rstrip() for line in raw]
    # A stream ends mid-line, so a last line with no newline after it may still be being
    # written and is not judged; a page ends in a newline, and that trailing blank is not
    # a line either. A loop is judged on the lines actually written whole.
    end = len(lines) - (0 if text.endswith("\n") else 1)
    while end > 0 and not lines[end - 1]:
        end -= 1
    lines = lines[:end]
    for period in range(1, config.TRANSCRIBE_LOOP_MAX_LINE_PERIOD + 1):
        # Each compared line equals the one `period` earlier, so `needed` comparisons over
        # `needed + period` lines: twenty-four identical lines for a row, four blocks for a
        # block of eight.
        needed = max(
            config.TRANSCRIBE_LOOP_LINES - period,
            (config.TRANSCRIBE_LOOP_MIN_LINE_REPEATS - 1) * period,
        )
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
    """A tail of `TRANSCRIBE_LOOP_CHARS` characters that repeats a short unit."""
    span = config.TRANSCRIBE_LOOP_CHARS
    for period in range(1, config.TRANSCRIBE_LOOP_MAX_CHAR_PERIOD + 1):
        if len(text) < span + period:
            break
        if not all(text[-i] == text[-i - period] for i in range(1, span + 1)):
            continue
        unit = text[-period:]
        if not unit.strip():
            continue
        k = len(text) - 1
        while k - period >= 0 and text[k] == text[k - period]:
            k -= 1
        return Loop(k - period + 1, unit)
    return None


@lru_cache(maxsize=8)
def _char_run_re(period: int, repeats: int) -> re.Pattern:
    """A character loop anywhere: the shortest unit of up to `period` characters repeated.

    The match is then measured against `TRANSCRIBE_LOOP_CHARS`. A lazy unit finds `\\_` before
    `\\_\\_`, and the repeat floor keeps the search from stopping at every doubled letter of
    ordinary prose.
    """
    return re.compile(r"(.{1,%d}?)\1{%d,}" % (period, repeats), re.DOTALL)


def signature() -> tuple[int, ...]:
    """The thresholds in force, for a memo of verdicts that must not outlive a change to them."""
    return (
        config.TRANSCRIBE_LOOP_LINES,
        config.TRANSCRIBE_LOOP_MAX_LINE_PERIOD,
        config.TRANSCRIBE_LOOP_MIN_LINE_REPEATS,
        config.TRANSCRIBE_LOOP_CHARS,
        config.TRANSCRIBE_LOOP_MAX_CHAR_PERIOD,
        config.TRANSCRIBE_LOOP_CHAR_RUN_REPEATS,
    )
