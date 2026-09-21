"""The two screens the commission's free text passes before it reaches the generator.

They are separate CALLS on purpose and the order is a closed decision — the guardrail is a
small local classifier reading the text alone with a 4096 window, the scope judge is handed
the graph's whole concept list, so a text that should reach no model at all must not reach
the larger of the two first. What they were not is separate SEQUENCES: the generator and the
evaluation each carried their own copy of the order, the two error sentences and the owner
derivation, and the evaluation reached into `variatio.runtime.generator` for a private helper to
format one of them. `screen_instructions` is that sequence, once.

Both fail open, each in its own way: an unreadable guardrail criterion is skipped and clears
`Verdict.checked`, and a judge that cannot answer returns `Ruling(checked=False)`. A screen
that blocks when its model is down blocks everything.
"""

from ... import wording as wording_sets
from ...core import progress
from . import admissibility, guardrail
from .admissibility import (
    SLOT_KEYS,
    Owner,
    Request,
    Ruling,
    Slot,
    catalog,
    owners,
    screen,
)
from .guardrail import Verdict, check, injection_pattern


class InstructionsBlocked(ValueError):
    """The free text was refused by one of the two screens.

    A `ValueError` still, so every caller that caught the block as one keeps doing so; what
    the subclass adds is `code`, which the job runner copies onto the job. A screen can
    then tell "the judge refused this text" from "the generator broke" without matching a
    sentence — the sentence is the workspace's, in either language, and matching it is
    what kept the block from ever reaching the form.
    """

    code = "instructions_blocked"


def screen_instructions(
    instructions: str | None,
    *,
    knowledge_graph,
    item_type,
    profile,
    content_context,
    concepts: list[str],
    prompts,
    step_prefix: str = "",
) -> Ruling:
    """Run both screens over one free-text field, in order, and return what it may ask for.

    Raises `InstructionsBlocked` when either screen blocks the commission. The raise stays INSIDE the
    step so a block marks that step failed: a green tick on "checking" beside a failed job
    would read as if something else broke.

    `step_prefix` is what tells the evaluation's steps from the pipeline's (`eval.guardrail`
    against `guardrail`); everything else is identical, which is the whole reason this is
    one function.
    """
    if not instructions:
        return Ruling(requests=(), checked=True)

    wording = wording_sets.beside(prompts)

    with progress.step(f"{step_prefix}guardrail", "Checking the instructions"):
        verdict = guardrail.check(instructions, wording=wording)
        if verdict.blocked:
            raise InstructionsBlocked(wording.guardrail_blocked(verdict.reason))

    with progress.step(f"{step_prefix}admissibility", "Checking the scope of the commission"):
        ruling = admissibility.screen(
            instructions,
            admissibility.owners(
                knowledge_graph, item_type, profile, content_context, concepts, wording
            ),
            concepts,
            prompts,
            content_context.prompt_block(),
        )
        if not ruling.ok:
            first = ruling.blocked[0]
            raise InstructionsBlocked(
                wording.scope_blocked(
                    first.text, first.owner.label, first.term, sentence_case(first.owner.where)
                )
            )
    return ruling


def sentence_case(text: str) -> str:
    """Upper-case the first letter and leave the rest alone.

    NOT `str.capitalize()`, which lowercases everything after it: an owner's `where`
    quotes a screen control by name, and capitalising it names one nobody can find.
    """
    return text[:1].upper() + text[1:]


__all__ = [
    "InstructionsBlocked",
    "SLOT_KEYS",
    "Owner",
    "Request",
    "Ruling",
    "Slot",
    "Verdict",
    "admissibility",
    "catalog",
    "check",
    "guardrail",
    "injection_pattern",
    "owners",
    "screen",
    "screen_instructions",
    "sentence_case",
]
