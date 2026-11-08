"""What a conversational function's turn job shares: a quiet stream, and freeing a conversation.

WHAT A TURN'S JOB SAYS IN PUBLIC IS NOTHING. The event stream is the workspace's, so every
member's screen hears a job's parameters and its result; a conversation is its author's
alone. A turn's job therefore names the conversation and the turn and carries no text either
way, and while it runs only its steps reach the stream (`QuietEmitter`): the guardrail
announces what it blocked and the repair quotes the answer it repairs, and neither is anybody
else's to hear.
"""

from . import store as shared


class QuietEmitter:
    """Let through only a turn's step events, and drop everything its calls say besides."""

    def __init__(self, inner):
        """Wrap the emitter the job publishes through."""
        self._inner = inner

    def emit(self, kind: str, payload: dict) -> None:
        """Forward the event only when it marks a step starting, moving or ending."""
        if kind.startswith("step."):
            self._inner.emit(kind, payload)

    def should_cancel(self) -> bool:
        """Defer the cancellation question to the emitter underneath."""
        return self._inner.should_cancel()


def release(store: shared.Store, ws, job, conversation_id: str, turn: int, reason: str) -> None:
    """Free a conversation whose turn will get no reply, saying why on the student's turn."""
    with store.lock_for(ws, job.user_id, conversation_id):
        record = store.get(ws, job.user_id, conversation_id)
        if record is None or (record.get("pending") or {}).get("job_id") != job.id:
            return
        shared.mark_failed(record, turn, reason)
        store.write(ws, job.user_id, record)
