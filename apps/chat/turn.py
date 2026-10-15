"""One turn of the free chat: a student's message in, the reply and its record out.

Two steps and no more (the user's decision, 2026-10-14):

1. The guardrail reads the message (`screening.screen_message`, the generation's own call). A
   refused message gets a fixed answer and reaches nothing else.
2. One call answers it, under the chat's system prompt — its role, its scope and the subject
   — with the recent conversation and, when the conversation was opened on an exercise, that
   exercise as the student reads it.

No classification, no card, no checks and no concept map. It takes plain data and returns
data: the conversation is the server's to read and to save.
"""

import time
from dataclasses import dataclass

from loguru import logger

from variatio.core import inference, progress
from variatio.runtime import screening

from . import BLOCKED, REPLIED
from . import config as chat_config
from . import prompts as chat_prompts_pkg


@dataclass(frozen=True)
class ChatResult:
    """The reply and what a saved turn keeps about how it was made."""

    text: str
    kind: str
    model: str | None = None
    effort: bool | str | None = None
    truncated: bool = False
    prompt: str | None = None
    elapsed_ms: int = 0

    def record(self) -> dict:
        """Return the turn as a conversation file keeps it, beside the reply's text."""
        return {
            "kind": self.kind,
            "model": self.model,
            "effort": self.effort,
            "truncated": self.truncated,
            "prompt": self.prompt,
            "elapsed_ms": self.elapsed_ms,
        }


def run_turn(
    *,
    language: str,
    prompts,
    subject: str,
    message: str,
    history: list[dict],
    exercise: list[tuple[str, str]] | None = None,
) -> ChatResult:
    """Answer one message of a conversation, following the two steps above.

    `prompts` is the workspace's prompt set (the guardrail's wording reads it), `subject` the
    subject's prompt block, `history` the conversation before this message as `{role, text}`
    turns, and `exercise` the fields of the exercise it was opened on, as labels and values.
    """
    started = time.perf_counter()
    chat_prompts = chat_prompts_pkg.of(language)

    screened = screening.screen_message(message, prompts=prompts, step_prefix="chat.")
    if screened.blocked:
        logger.info(f"[chat] Mensaje rechazado por el guardián ({screened.blocked_by})")
        return ChatResult(
            text=chat_prompts.blocked_reply(),
            kind=BLOCKED,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )

    turns = chat_config.HISTORY_TURNS
    pairs = [
        (str(t.get("role") or "student"), str(t.get("text") or ""))
        for t in (history[-2 * turns :] if turns else [])
    ]
    prompt = chat_prompts.turn_prompt(
        pairs, message, chat_prompts.exercise_block(exercise) if exercise else None
    )
    model, think = chat_config.REPLY_MODEL, chat_config.THINK_REPLY
    progress.checkpoint()
    with progress.step("chat.reply", "Writing the reply"):
        response = inference.generate(
            model=model,
            prompt=prompt,
            system=chat_prompts.system_prompt(subject),
            think=think,
            sampling=inference.sampling("chat_reply", think),
            max_output_tokens=None if think else chat_config.REPLY_MAX_TOKENS,
        )
    text = inference.split_thinking(response.response or "").response.strip()
    return ChatResult(
        text=text,
        kind=REPLIED,
        model=model,
        effort=think,
        truncated=bool(response.truncated),
        prompt=prompt,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
    )
