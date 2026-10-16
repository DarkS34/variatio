"""One page asked of the vision model: the call, its one noted retry, and the page salvaged
when the answer stays unfinished.
"""

import re

from loguru import logger

from .... import config, wording as wording_sets
from ....core import inference, repetition
from ....prompts.marks import EMPTY_PAGE_MARK


MD_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", re.DOTALL)


def _transcribe_page(
    image: str, index: int, count: int, model: str, tag: str, prompts
) -> str:
    """Transcribe one page image, marking the page when it cannot be read whole.

    An answer that never finished — a repetition the engine stopped reading, or one that
    ran to `TRANSCRIBE_MAX_OUTPUT_TOKENS` — is asked for ONCE MORE with the prompt saying
    what went wrong (`_ask_twice`); what the second attempt still cannot finish is kept up
    to the loop under the failure marker (`_salvaged_page`). Kept as it came, a cut answer
    was measured costing the profile and the bank more than the page itself; thrown away
    whole, it took a title and a paragraph down with the grid that broke it.
    """
    what = f"page {index}/{count}"
    try:
        answer = _ask_twice(
            model,
            lambda note: prompts.transcribe_page_prompt(index, count, note=note),
            image,
            "transcribe",
            config.THINK_TRANSCRIBE,
            tag,
            what,
            prompts,
        )
    except inference.InferenceError as e:
        logger.error(f"{tag}{what}: giving up after the retries ({e})")
        # A lost page is lost exercises. Leave a marker a human will trip over in the
        # cached file rather than a silent gap that looks like a page with nothing on it.
        return wording_sets.beside(prompts).failed_page(index, count, str(e))
    if _unfinished(answer):
        return _salvaged_page(answer, index, count, tag, prompts)
    page = _unwrap_markdown_fence(answer.response)
    stripped = page.strip()
    # Tolerant on purpose: models wrap the sentinel in backticks, or add a full stop.
    # Anything that is only the sentinel plus punctuation is an empty page.
    if not stripped or (
        EMPTY_PAGE_MARK in stripped and len(stripped) <= len(EMPTY_PAGE_MARK) + 16
    ):
        return ""
    return page


def _ask_twice(
    model: str, build_prompt, image: str, phase: str, think, tag: str, what: str, prompts
) -> inference.GenerationResponse:
    """Ask once, and once more with the prompt saying what went wrong when the answer never finished.

    The same request at temperature 0 is the same loop — measured three times over on one
    page — and a request that names what the model kept writing and restates the rule for
    drawn elements is a different one (`transcribe_retry_note`). Two attempts and never a
    third: a page that locks twice under two prompts is a page for a person. When both
    fail the one that read further before locking is returned, since that is what the
    caller keeps.
    """
    answer = _ask(model, build_prompt(""), image, phase, think, tag, what)
    if not _unfinished(answer):
        return answer
    cap = config.TRANSCRIBE_MAX_OUTPUT_TOKENS
    logger.warning(f"{tag}{what}: {_cause(answer, cap)}; asking once more with the rule spelled out")
    repeated = repetition.quoted(answer.loop) if answer.loop else None
    note = prompts.transcribe_retry_note(repeated, cap)
    again = _ask(model, build_prompt(note), image, phase, think, tag, what)
    if not _unfinished(again):
        return again
    return again if len(_head(again)) >= len(_head(answer)) else answer


def _ask(
    model: str, prompt: str, image: str, phase: str, think, tag: str, what: str
) -> inference.GenerationResponse:
    """One transcription call, retried on an engine error up to `TRANSCRIBE_MAX_RETRIES` times.

    Only an `InferenceError` is retried, the engine having not answered at all. An answer
    that never finished is an answer to this function; `_ask_twice` decides what it costs.
    Every call asks the engine to stop on a repetition, which is what makes a loop cost
    seconds on the local route instead of a whole output budget.
    """
    last_error: inference.InferenceError | None = None
    for _attempt in range(config.TRANSCRIBE_MAX_RETRIES + 1):
        try:
            return inference.generate(
                model=model,
                prompt=prompt,
                think=think,
                images=[image],
                sampling=inference.sampling(phase, think),
                max_output_tokens=config.TRANSCRIBE_MAX_OUTPUT_TOKENS,
                stop_on_loop=True,
            )
        except inference.InferenceError as e:
            last_error = e
            logger.warning(f"{tag}{what}: transcription failed ({e})")
    assert last_error is not None
    raise last_error


def _unfinished(answer: inference.GenerationResponse) -> bool:
    """Whether the answer stopped for a reason other than the model finishing."""
    return answer.loop is not None or answer.truncated


def _cause(answer: inference.GenerationResponse, cap: int) -> str:
    """One clause for the log naming why the answer did not finish."""
    if answer.loop is not None:
        return f"answer stopped on a repetition of «{repetition.quoted(answer.loop)}»"
    return f"answer cut at the {cap}-token cap after {len(answer.response)} characters"


def _head(answer: inference.GenerationResponse) -> str:
    """What the model read before it stopped saying anything new: the text up to the loop."""
    text = answer.response
    found = repetition.detect(text)
    return repetition.cut(text, found) if found is not None else text.rstrip()


def _salvaged_page(
    answer: inference.GenerationResponse, index: int, count: int, tag: str, prompts
) -> str:
    """The failure marker over whatever the model read before it stopped finishing.

    The marker comes FIRST, so `failed_pages` counts the page and the screen draws it red;
    the head follows, so a title or a paragraph read before a grid is not thrown away
    with the grid. The marker says whether anything follows, and that the rest of the
    page is a person's to transcribe.
    """
    cap = config.TRANSCRIBE_MAX_OUTPUT_TOKENS
    head = _head(answer).strip()
    logger.error(
        f"{tag}page {index}/{count}: {_cause(answer, cap)} on the second attempt too; "
        f"marked as failed, {len(head)} character(s) kept"
    )
    marker = wording_sets.beside(prompts).failed_page_unfinished(
        index,
        count,
        repetition.quoted(answer.loop) if answer.loop else None,
        cap,
        bool(head),
    )
    return f"{marker}\n\n{head}" if head else marker


def _unwrap_markdown_fence(text: str) -> str:
    """Strip the ```markdown wrapper some models put around a whole page."""
    match = MD_FENCE_RE.match(text.strip())
    return match.group(1) if match else text.strip()
