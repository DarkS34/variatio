"""Which kind of message a student wrote, decided by the cheapest thing that can decide it.

The kind decides the card and, for two of them, the whole answer: an administrative question
and one outside the subject get a fixed text and never reach the reply model. Three layers,
in order, each only when the one before cannot answer:

1. Signals in the artifacts, with no model call. A message the bank recognises as one of its
   exercises IS help with an exercise, and so is the first message of a conversation opened
   from a generated one.
2. One call to the reply model under a grammar that admits only the kinds, without
   reasoning — the GPU already holds that model for the reply that follows.
3. Failing open: a call that cannot be read is a question about the theory, which is the
   kind whose card carries the most and whose reply is never a fixed text.

The graph has the last word on one verdict: a message the model calls off-topic but whose
best concept clears the focus threshold IS about the subject, and is answered as theory. The
focus threshold and not the syllabus one, because a message is one sentence: measured, a
greeting reaches 0.49 against some concept, past the syllabus's 0.40.
"""

from dataclasses import dataclass

import numpy as np
from loguru import logger

from variatio.core import inference, progress

from . import EXERCISE, KINDS, OFF_TOPIC, THEORY, calls

# The answer is one word inside a tiny object; the cap only stops a model that keeps going.
_CLASSIFY_MAX_TOKENS = 64

BANK = "bank"
OPENED = "opened"
MODEL = "model"
GRAPH = "graph"
DEFAULT = "default"


@dataclass(frozen=True)
class Classification:
    """A message's kind, which layer decided it, and the bank exercise it matched if any."""

    kind: str
    decided_by: str
    exercise_id: str | None = None
    exercise_score: float | None = None


def classify(
    message: str,
    *,
    concept_scores: dict[str, float],
    context,
    tutor_prompts,
    model: str,
    last_reply: str | None,
    opened_from_exercise: bool,
    bank_threshold: float,
    concept_threshold: float,
) -> Classification:
    """Decide the kind of one message, the cheapest layer first."""
    match = bank_match(message, context.embedder)
    if match is not None and match[1] >= bank_threshold:
        return Classification(EXERCISE, BANK, exercise_id=match[0], exercise_score=round(match[1], 4))
    if opened_from_exercise:
        return Classification(EXERCISE, OPENED)

    graph = context.knowledge_graph
    with progress.step("tutor.classify", "Classifying the message"):
        answer = None
        try:
            answer = calls.ask_object(
                tutor_prompts.classify_prompt(
                    context.content_context.prompt_block(), list(graph.domains), last_reply, message
                ),
                {
                    "type": "object",
                    "properties": {"kind": {"type": "string", "enum": list(KINDS)}},
                    "required": ["kind"],
                },
                model=model,
                think=False,
                phase="tutor_classify",
                tutor_prompts=tutor_prompts,
                prompts=context.prompts,
                max_output_tokens=_CLASSIFY_MAX_TOKENS,
            )
        except inference.InferenceError as exc:
            logger.warning(f"[tutor] La clasificación falló ({exc}); se trata como teoría")

    kind = (answer or {}).get("kind")
    if kind not in KINDS:
        return Classification(THEORY, DEFAULT)
    if kind == OFF_TOPIC and max(concept_scores.values(), default=0.0) >= concept_threshold:
        return Classification(THEORY, GRAPH)
    return Classification(kind, MODEL)


def bank_match(message: str, embedder) -> tuple[str, float] | None:
    """Return the bank exercise closest to a message and its score, or None with no bank.

    Compared on the DOCUMENT side, the side the bank was embedded on, because the question
    is "is this the same text" and not "what is it about": measured on the demo workspace, a
    pasted statement scores 1.0 there (0.97 with a sentence before it) against 0.66 on the
    query side, where an unrelated request scored 0.65 too. Against every embedded item and
    not only those with a primary concept: a pasted statement is recognised whether or not
    the tagger settled it.
    """
    vector = embedder.embed_document(message)
    best: tuple[str, float] | None = None
    for item_id, item_vector in embedder.exemplars_bank_index.items():
        score = float(np.dot(item_vector, vector))
        if best is None or score > best[1]:
            best = (item_id, score)
    return best
