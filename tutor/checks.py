"""What code checks in a reply before a student reads it.

The method is in the prompt, and a prompt is a request: these are the parts of it a machine
can verify without a judge, so they are verified rather than hoped for. Each check names one
rule of the method, and a failure is a code the retry note turns back into the rule:

- a reply asks at least one question and not more than the cap (`no_question`,
  `too_many_questions`);
- it carries no more lines of code than the cap — enough to quote one line of the student's
  (`code`);
- it does not copy a passage of its own card for more than a few words running: the notes are
  pointed to, not pasted (`copied`);
- it does not name a concept the card listed as coming later, unless the student brought it
  up (`later`);
- it does not suggest a statement the subject's criteria rule out: in code at all, in prose
  only when the student did not write it first — explaining why `break` is avoided is the
  method, suggesting it is not (`forbidden`);
- no sentence of it opens by telling the student they are right — «Sí, exacto», «Correcto»
  — which is the one way of validating an answer a pattern can see (`validated`);
- it is not empty and was not cut by the output cap (`empty`, `truncated`).

What no check can see — whether a reply SAYS a solution in prose, or tells the student they
are right — stays the prompt's, and the retry's note cannot help with it.
"""

import re

from variatio.core.lexicon import fold, mentions

_FENCE = re.compile(r"```[^\n]*\n(.*?)(?:```|\Z)", re.DOTALL)
_INLINE = re.compile(r"`([^`\n]+)`")
_WORD = re.compile(r"\w+")


def check_reply(
    text: str,
    *,
    quotes: list[str],
    later: list[str],
    forbidden_terms: list[str],
    student_texts: list[str],
    truncated: bool,
    max_questions: int,
    max_code_lines: int,
    copy_max_words: int,
    validation: str | None = None,
    wording=None,
) -> list[tuple[str, dict]]:
    """Return the method's rules this reply breaks, as `(code, data)` for the retry's note."""
    if not text.strip():
        return [("empty", {})]
    failures: list[tuple[str, dict]] = []
    if truncated:
        failures.append(("truncated", {}))

    questions = text.count("?")
    if questions == 0:
        failures.append(("no_question", {}))
    elif questions > max_questions:
        failures.append(("too_many_questions", {}))

    if code_lines(text) > max_code_lines:
        failures.append(("code", {}))

    if any(longest_shared_run(text, quote) > copy_max_words for quote in quotes):
        failures.append(("copied", {}))

    said = "\n".join(student_texts)
    introduced = [
        name for name in later if mentions(text, name, wording) and not mentions(said, name, wording)
    ]
    if introduced:
        failures.append(("later", {"concepts": ", ".join(f"«{name}»" for name in introduced)}))

    suggested = suggested_terms(text, forbidden_terms, said)
    if suggested:
        failures.append(("forbidden", {"terms": ", ".join(suggested)}))

    if validation and re.search(validation, fold(text).strip()):
        failures.append(("validated", {}))
    return failures


def code_lines(text: str) -> int:
    """Return how many non-blank lines the reply's fenced code blocks hold."""
    return sum(
        1 for block in _FENCE.findall(text) for line in block.splitlines() if line.strip()
    )


def longest_shared_run(text: str, other: str) -> int:
    """Return the length, in words, of the longest run the two texts share word for word.

    Folded first, so an accent or a capital does not hide a copy. Quadratic in the words of
    the two texts, which are a reply and a passage: a few hundred each.
    """
    a = _WORD.findall(fold(text))
    b = _WORD.findall(fold(other))
    if not a or not b:
        return 0
    best = 0
    previous = [0] * (len(b) + 1)
    for word in a:
        current = [0] * (len(b) + 1)
        for j, other_word in enumerate(b, 1):
            if word == other_word:
                current[j] = previous[j - 1] + 1
                if current[j] > best:
                    best = current[j]
        previous = current
    return best


def suggested_terms(text: str, terms: list[str], said: str) -> list[str]:
    """Return the forbidden terms the reply suggests: in its code always, in prose when unprompted."""
    code = "\n".join(_FENCE.findall(text) + _INLINE.findall(text))
    prose = _INLINE.sub(" ", _FENCE.sub(" ", text))
    found = []
    for term in terms:
        if _has_term(code, term) or (_has_term(prose, term) and not _has_term(said, term)):
            found.append(term)
    return found


def _has_term(text: str, term: str) -> bool:
    """Return whether `text` holds `term` as a whole word, regardless of case and accents."""
    needle = fold(term).strip()
    return bool(needle) and re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", fold(text)) is not None
