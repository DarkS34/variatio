"""One turn of a conversation: a student's message in, the tutor's reply and its record out.

The sequence is fixed, and every step is the cheapest one that can still decide:

1. The guardrail reads the message (`screening.screen_message`, the generation's own call). A
   refused message gets a fixed answer and reaches nothing else.
2. The message is embedded on the query side once, and that vector finds both the concepts
   it is about and the passages of the notes it is closest to; the bank, embedded on the
   document side, is compared on that side (`classify.bank_match`).
3. The kind is decided (`classify`). An administrative question and one outside the subject
   are answered by code with a fixed text.
4. The focus moves only if the message is clearly about something else (`focus`).
5. The card is written from the artifacts (`card`).
6. The reply model answers under the method, and code checks the answer (`checks`). A broken
   answer is asked again ONCE, with a note naming the rules it broke; a second failure sends a
   fixed question built from the card instead, so a student never reads a reply that broke
   the method.

It takes objects and returns data. It knows no file and writes nothing: the conversation is
the server's to read and to save, as a generated exercise is.
"""

import time
from dataclasses import dataclass, field

from loguru import logger

from variatio.core import inference, progress
from variatio.runtime import screening
from variatio import wording as wording_sets

from . import ADMINISTRATIVE, BLOCKED, OFF_TOPIC, SOCIAL, card, checks, classify, focus
from . import config as tutor_config
from . import prompts as tutor_prompts_pkg
from .criteria import Criteria
from .passages import PassageIndex


@dataclass(frozen=True)
class TurnResult:
    """The tutor's reply and everything a saved turn keeps about how it was made."""

    text: str
    kind: str
    decided_by: str
    state: dict
    references: list[dict] = field(default_factory=list)
    card: dict | None = None
    checks: dict = field(default_factory=dict)
    retried: bool = False
    fallback: bool = False
    model: str | None = None
    effort: bool | str | None = None
    prompt: str | None = None
    elapsed_ms: int = 0

    def record(self) -> dict:
        """Return the turn as a conversation file keeps it, beside the reply's text."""
        return {
            "kind": self.kind,
            "decided_by": self.decided_by,
            "references": self.references,
            "card": self.card,
            "checks": self.checks,
            "retried": self.retried,
            "fallback": self.fallback,
            "model": self.model,
            "effort": self.effort,
            "prompt": self.prompt,
            "elapsed_ms": self.elapsed_ms,
        }


def run_turn(
    context,
    *,
    sources: dict,
    criteria: Criteria,
    index: PassageIndex,
    message: str,
    history: list[dict],
    state: dict,
    given_focus: list[str] | None = None,
) -> TurnResult:
    """Answer one message of a conversation, following the sequence above.

    `history` is the conversation before this message, as `{role, text}` turns; `state` its
    focus, trail and checked concepts; `given_focus` the concepts the conversation was opened
    on, when it was opened from a generated exercise.
    """
    started = time.perf_counter()
    tutor_prompts = tutor_prompts_pkg.of(context.language)
    wording = wording_sets.beside(context.prompts)
    state = {"focus": [], "trail": [], "verified": [], **(state or {})}

    def done(text: str, kind: str, decided_by: str, **extra) -> TurnResult:
        """Close the turn with its elapsed time."""
        return TurnResult(
            text=text,
            kind=kind,
            decided_by=decided_by,
            state=extra.pop("next_state", state),
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            **extra,
        )

    screened = screening.screen_message(message, prompts=context.prompts, step_prefix="tutor.")
    if screened.blocked:
        logger.info(f"[tutor] Mensaje rechazado por el guardián ({screened.blocked_by})")
        return done(tutor_prompts.blocked_reply(), BLOCKED, "guardrail")

    vector = context.embedder.embed_query(message)
    scores = context.embedder.concept_scores(vector)
    last_reply = next((t["text"] for t in reversed(history) if t.get("role") == "tutor"), None)
    classified = classify.classify(
        message,
        concept_scores=scores,
        context=context,
        tutor_prompts=tutor_prompts,
        model=tutor_config.CLASSIFY_MODEL,
        last_reply=last_reply,
        opened_from_exercise=bool(given_focus) and not history,
        bank_threshold=tutor_config.BANK_MATCH_THRESHOLD,
        concept_threshold=tutor_config.FOCUS_THRESHOLD,
    )
    logger.info(f"[tutor] Mensaje de tipo «{classified.kind}» (decidido por {classified.decided_by})")

    graph = context.knowledge_graph
    if classified.kind == ADMINISTRATIVE:
        return done(criteria.administrative_reply, classified.kind, classified.decided_by)
    if classified.kind == OFF_TOPIC:
        subject = context.content_context.facts.get("subject", "")
        offer = tutor_prompts.off_topic_reply(subject, list(graph.domains))
        return done(offer, classified.kind, classified.decided_by)

    given = given_focus if (given_focus and not history) else None
    if classified.exercise_id:
        item = context.exemplars_bank.get(classified.exercise_id) or {}
        given = [c for c in [item.get("primary_concept"), *(item.get("concepts") or [])] if c]
    eligible = set(graph.all_concepts) - set(graph.generic_non_taggable_concepts)
    current = state["focus"]
    if classified.kind != SOCIAL:
        current = focus.next_focus(
            state["focus"],
            scores,
            threshold=tutor_config.FOCUS_THRESHOLD,
            margin=tutor_config.FOCUS_MARGIN,
            eligible=eligible,
            given=given,
        )

    the_card = card.assemble(
        classified.kind,
        context=context,
        sources=sources,
        criteria=criteria,
        index=index,
        vector=vector,
        focus=current,
        verified=state["verified"],
        exercise_id=classified.exercise_id,
    )
    turns = tutor_config.HISTORY_TURNS
    pairs = [
        (t.get("role", "student"), str(t.get("text") or ""))
        for t in (history[-2 * turns :] if turns else [])
    ]
    prompt = tutor_prompts.turn_prompt(
        tutor_prompts.card_block(the_card), pairs, message, classified.kind
    )
    model, think = tutor_config.REPLY_MODEL, tutor_config.THINK_REPLY
    student_texts = [str(t.get("text") or "") for t in history if t.get("role") == "student"] + [message]

    text, attempts = _reply(prompt, the_card, student_texts, tutor_prompts, wording, model, think)
    failures = attempts[-1]
    fallback = bool(failures)
    if fallback:
        first = the_card.focus[0] if the_card.focus else None
        place = (first.anchors[0].location if first and first.anchors else None) or next(
            (q.location for q in the_card.passages if q.location), None
        )
        text = tutor_prompts.fallback_reply(first.name if first else None, place)
        logger.warning(
            f"[tutor] Dos respuestas incumplieron el método ({', '.join(c for c, _ in failures)}); "
            "se envía la pregunta de reserva"
        )

    prerequisites = [p.name for concept in the_card.focus for p in concept.prerequisites]
    return done(
        text,
        classified.kind,
        classified.decided_by,
        next_state=focus.after_reply(state, current, prerequisites, text, wording),
        references=the_card.references(),
        card={
            **the_card.record(),
            **({"exercise_score": classified.exercise_score} if classified.exercise_score else {}),
        },
        checks={
            "attempts": [[code for code, _ in found] for found in attempts],
            "questions": text.count("?"),
        },
        retried=len(attempts) > 1,
        fallback=fallback,
        model=model,
        effort=think,
        prompt=prompt,
    )


def _reply(
    prompt: str, the_card, student_texts: list[str], tutor_prompts, wording, model: str, think
) -> tuple[str, list[list[tuple[str, dict]]]]:
    """Ask for the reply, check it, and ask once more with a note when it broke the method.

    Returns the last text and, per attempt, the rules it broke: the last list is empty when
    the reply passed, and a second list means a second attempt was made.
    """
    system = tutor_prompts.method(tutor_config.MAX_QUESTIONS)
    note = ""
    attempts: list[list[tuple[str, dict]]] = []
    text = ""
    for attempt in (1, 2):
        progress.checkpoint()
        with progress.step(f"tutor.reply.{attempt}", "Writing the reply"):
            response = inference.generate(
                model=model,
                prompt=prompt + note,
                system=system,
                think=think,
                sampling=inference.sampling("tutor_reply", think),
                max_output_tokens=None if think else tutor_config.REPLY_MAX_TOKENS,
            )
        text = inference.split_thinking(response.response or "").response.strip()
        failures = checks.check_reply(
            text,
            quotes=[quote.text for quote in the_card.quotes()],
            later=the_card.later(),
            forbidden_terms=list(the_card.forbidden_terms),
            student_texts=student_texts,
            truncated=response.truncated,
            max_questions=tutor_config.MAX_QUESTIONS,
            max_code_lines=tutor_config.MAX_CODE_LINES,
            copy_max_words=tutor_config.COPY_MAX_WORDS,
            validation=tutor_prompts.VALIDATION_PATTERN,
            wording=wording,
        )
        attempts.append(failures)
        if not failures:
            return text, attempts
        logger.info(
            f"[tutor] La respuesta {attempt} incumple el método: {', '.join(c for c, _ in failures)}"
        )
        note = tutor_prompts.retry_note(
            failures, tutor_config.MAX_QUESTIONS, tutor_config.MAX_CODE_LINES
        )
    return text, attempts
