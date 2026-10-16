"""Joining the transcribed pages back into one text, and deciding each seam between two.

Deterministic first; the `transcribe_seam` model only classifies an ambiguous seam, never
rewrites one, and fails open.
"""

import re
from collections.abc import Iterator

from json_repair import repair_json
from loguru import logger

from .... import config
from ....core import inference, progress
from ....prompts.marks import SEAM_SEPARATORS
from ..markdown import page_mark


def seams_merged(seams) -> int:
    """How many seams were joined as a continuation rather than as a paragraph break."""
    return sum(
        1
        for record in valid_seams(seams)
        if record.get("separator", PARAGRAPH) != PARAGRAPH
    )


def seams_failed(seams) -> list[int]:
    """The pages whose seam the model could not review."""
    return [record["page"] for record in valid_seams(seams) if record.get("failed")]


# THE SEAM BETWEEN TWO PAGES ----------------------------------------------------------------------
#
# A page break is a fact about the paper and not about the text, so what has to be decided
# per seam is how much of a break it really is: joining every pair with a paragraph break
# cuts an exercise that spans two pages in half, closes a code fence in the middle of the
# block and loses the second half of a table.

SEPARATORS = {"none": "", "space": " ", "newline": "\n", "paragraph": "\n\n"}


PARAGRAPH = "paragraph"


NEWLINE = "newline"


SPACE = "space"


# A cap, not a knob: beyond a handful of lines the answer stops being "a repeated header"
# and starts being "a page I decided to drop", and losing content is the one failure this
# whole route exists to avoid.
MAX_SEAM_DROP_LINES = 3


_FENCE_LINE_RE = re.compile(r"^\s*```")


_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s")


_BULLET_LINE_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


_TABLE_DIVIDER_RE = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$")


_SENTENCE_END_RE = re.compile(r"[.!?:;…]['\"»”)\]]*$")


_CONTINUATION_HEADS = ",;:)]}»…"


def join_pages(pages: list[str], seams: list[dict] | None = None) -> str:
    """The pages as one markdown document, each seam closed as tightly as it deserves."""
    return "".join(_stitched(pages, seams))


def page_starts(pages: list[str], seams: list[dict] | None = None) -> list[int]:
    """Where each page begins in what `join_pages` returns: one offset per page.

    A page's start is where its separator starts, so anything of its own body lies after
    it; a page that adds nothing starts where the next one does.
    """
    starts: list[int] = []
    length = 0
    for piece in _stitched(pages, seams):
        starts.append(length)
        length += len(piece)
    return starts


def _stitched(pages: list[str], seams: list[dict] | None) -> Iterator[str]:
    """Yield what each page adds to the joined document: its separator, its mark, its body."""
    decided = {record["page"]: record for record in valid_seams(seams)}
    out = ""
    for index, page in enumerate(pages, 1):
        body = _trim(page)
        if not body:
            yield ""
            continue
        if not out:
            out = body
            yield body
            continue
        separator, certain = seam(out, body)
        record = decided.get(index)
        if record is not None and not certain:
            if record.get("separator") in SEPARATORS:
                separator = str(record["separator"])
            body = _drop_lines(body, _clamp_drop(record.get("drop_head_lines")))
        if separator == NEWLINE:
            body = (
                _drop_reopened_fence(body)
                if fence_is_open(out)
                else _drop_repeated_header(body)
            )
        if not body.strip():
            yield ""
            continue
        if separator == PARAGRAPH:
            piece = f"\n\n{page_mark(index)}\n\n{body}"
        else:
            piece = f"{SEPARATORS[separator]}{body}"
        out = f"{out}{piece}"
        yield piece


def valid_seams(records) -> list[dict]:
    """Keep the stored seam records that at least name the page they belong to."""
    if not isinstance(records, list):
        return []
    out = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("page"), int):
            continue
        out.append(record)
    return out


def seam(left: str, right: str) -> tuple[str, bool]:
    """`(separator key, certain)` for the boundary between two consecutive pages."""
    if not left.strip() or not right.strip():
        return PARAGRAPH, True
    # An unbalanced fence is the one case that needs no judgement: the block is open, so the
    # next page is inside it whatever it looks like.
    if fence_is_open(left):
        return NEWLINE, True
    tail, head = _last_line(left), _first_line(right)
    if (
        _TABLE_ROW_RE.match(tail)
        and _TABLE_ROW_RE.match(head)
        and not _TABLE_DIVIDER_RE.match(head)
    ):
        return NEWLINE, False
    if _continues_sentence(tail, head):
        return SPACE, False
    return PARAGRAPH, False


def fence_is_open(text: str) -> bool:
    """Say whether the text ends inside a code fence."""
    return sum(1 for line in text.splitlines() if _FENCE_LINE_RE.match(line)) % 2 == 1


def _last_line(text: str) -> str:
    """The last line with anything on it."""
    return next((line for line in reversed(text.splitlines()) if line.strip()), "")


def _first_line(text: str) -> str:
    """The first line with anything on it."""
    return next((line for line in text.splitlines() if line.strip()), "")


def _continues_sentence(tail: str, head: str) -> bool:
    """Say whether the second page's first line carries on the first page's last one."""
    if _HEADING_LINE_RE.match(tail) or _BULLET_LINE_RE.match(tail):
        return False
    if _TABLE_ROW_RE.match(tail) or _FENCE_LINE_RE.match(tail):
        return False
    if _SENTENCE_END_RE.search(tail.rstrip()):
        return False
    if _HEADING_LINE_RE.match(head) or _BULLET_LINE_RE.match(head):
        return False
    if _TABLE_ROW_RE.match(head) or _FENCE_LINE_RE.match(head):
        return False
    first = head.lstrip()[:1]
    return bool(first) and (first.islower() or first in _CONTINUATION_HEADS)


def _drop_lines(text: str, count: int) -> str:
    """Remove the first `count` non-blank lines of a page."""
    if count <= 0:
        return text
    lines = text.splitlines()
    dropped, index = 0, 0
    while index < len(lines) and dropped < count:
        if lines[index].strip():
            dropped += 1
        index += 1
    return _trim("\n".join(lines[index:]))


def _clamp_drop(value) -> int:
    """Read the model's line count as an integer within the cap, `0` for anything else."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_SEAM_DROP_LINES))


def _drop_reopened_fence(text: str) -> str:
    """Remove an opening fence a page repeated for a code block that is already open."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if _FENCE_LINE_RE.match(line):
            return _trim("\n".join(lines[:index] + lines[index + 1 :]))
        return text
    return text


def _drop_repeated_header(text: str) -> str:
    """Remove the header row and divider a page repeated for a table that continues."""
    lines = text.splitlines()
    body = [index for index, line in enumerate(lines) if line.strip()]
    if len(body) < 2:
        return text
    first, second = body[0], body[1]
    if _TABLE_ROW_RE.match(lines[first]) and _TABLE_DIVIDER_RE.match(lines[second]):
        return _trim("\n".join(lines[:first] + lines[second + 1 :]))
    return text


def _trim(text: str) -> str:
    """Drop leading and trailing blank LINES, keeping the indentation of what survives.

    `strip()` would take the indentation of the first surviving line with them, and a page
    that continues a code block starts indented — flattening it is the corruption the whole
    page-image route exists to avoid.
    """
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


# THE SEAM, REVIEWED BY THE MODEL ------------------------------------------------------------------
#
# The model CLASSIFIES a seam and never rewrites a character: the transcription prompt is
# built on "copy character by character", and a second model allowed to redraft would undo
# it. All it may say is how the two pages are glued and how many of the second one's opening
# lines are repeated layout.

SEAM_SCHEMA = {
    "type": "object",
    "properties": {
        "continues": {"type": "boolean"},
        "separator": {"type": "string", "enum": list(SEAM_SEPARATORS)},
        "drop_head_lines": {"type": "integer"},
        "reason": {"type": "string"},
    },
    "required": ["continues", "separator", "drop_head_lines"],
}


def review_seams(
    pages: list[str],
    prompts,
    model: str = "",
    tag: str = "",
    only: set[int] | None = None,
) -> list[dict]:
    """Ask the model about every seam the deterministic rule could not settle.

    `only` limits the question to the seams named after those pages — the two around a page
    that was just read again — so the rest keep the answers already paid for.
    """
    model = model or config.TRANSCRIBE_SEAM_MODEL
    boundaries = [
        boundary for boundary in _boundaries(pages) if only is None or boundary[2] in only
    ]
    if not boundaries:
        return []
    records: list[dict] = []
    with progress.step(
        "transcribe_seam", "Checking the seams between pages", len(boundaries)
    ) as reporter:
        for done, (left, right, index) in enumerate(boundaries, 1):
            progress.checkpoint()
            reporter.start(done, detail=f"costura {index - 1}→{index}")
            record = _review_seam(left, right, index, len(pages), model, tag, prompts)
            if record is not None:
                records.append(record)
    merged = sum(1 for record in records if record.get("separator", PARAGRAPH) != PARAGRAPH)
    if records:
        logger.info(f"{tag}{merged}/{len(boundaries)} seam(s) joined as a continuation")
    return records


def _boundaries(pages: list[str]) -> list[tuple[str, str, int]]:
    """The `(left, right, index)` seams between consecutive pages that have content."""
    out: list[tuple[str, str, int]] = []
    previous: str | None = None
    for index, page in enumerate(pages, 1):
        if not page.strip():
            continue
        if previous is not None:
            out.append((previous, page, index))
        previous = page
    return out


def _review_seam(
    left: str, right: str, index: int, count: int, model: str, tag: str, prompts
) -> dict | None:
    """Have the model classify one uncertain seam, failing open onto the rule.

    An engine that raises and an unreadable answer both record the seam as failed and leave
    the deterministic separator in place: one seam is never a reason to throw away a
    forty-page transcription.
    """
    if seam(left, right)[1]:
        return None
    tail = left.strip()[-config.TRANSCRIBE_SEAM_CHARS :]
    head = right.strip()[: config.TRANSCRIBE_SEAM_CHARS]
    if not tail or not head:
        return None
    try:
        response = inference.generate(
            model=model,
            prompt=prompts.merge_pages_prompt(tail, head, index, count),
            think=config.THINK_TRANSCRIBE_SEAM,
            format=None if config.THINK_TRANSCRIBE_SEAM else SEAM_SCHEMA,
            sampling=inference.sampling("transcribe_seam", config.THINK_TRANSCRIBE_SEAM),
        ).response
    except inference.InferenceError as e:
        logger.warning(f"{tag}seam {index - 1}→{index}: not reviewed ({e}); joined by rule")
        return {"page": index, "failed": True}
    parsed = _parse_seam(response)
    if parsed is None:
        logger.warning(
            f"{tag}seam {index - 1}→{index}: unreadable answer; joined by rule"
        )
        return {"page": index, "failed": True}
    return {"page": index, **parsed}


def _parse_seam(response: str) -> dict | None:
    """Read the seam answer, keeping only a separator the catalogue actually holds."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
    try:
        raw = repair_json(cleaned, return_objects=True)
    except (ValueError, TypeError):
        return None
    if not isinstance(raw, dict) or raw.get("separator") not in SEAM_SEPARATORS:
        return None
    return {
        "separator": str(raw["separator"]),
        "drop_head_lines": _clamp_drop(raw.get("drop_head_lines")),
    }
