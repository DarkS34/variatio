"""Keep a model's `<think>…</think>` deliberation out of its answer, whole or chunk by chunk."""

from .types import GenerationResponse

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"
_MAX_TAG = max(len(THINK_OPEN), len(THINK_CLOSE))


def split_thinking(
    text: str,
    sdk_thinking: str | None = None,
    truncated: bool = False,
    loop: str | None = None,
) -> GenerationResponse:
    """Same split as the streaming path, for a response that arrived in one piece."""
    splitter = ThinkingSplitter()
    answer: list[str] = []
    thinking: list[str] = [sdk_thinking.strip()] if (sdk_thinking or "").strip() else []
    
    for part, channel in [*splitter.feed(text or ""), *splitter.flush()]:
        (thinking if channel == "thinking" else answer).append(part)
    
    return GenerationResponse(
        response="".join(answer).strip(),
        thinking="\n\n".join(p.strip() for p in thinking if p.strip()) or None,
        truncated=truncated,
        loop=loop,
    )


class ThinkingSplitter:
    """Routes `<think>…</think>` out of the answer, chunk by chunk.

    Some models report their reasoning in the SDK's own `thinking` field; others just
    print the tags inline in the response. Without this the inline ones flood the answer
    pane with their scratchpad and the final parse has to guess which of the JSON blobs
    they wrote along the way was the actual answer.

    Chunks arrive at arbitrary boundaries, so a tag can be cut in half between two of
    them: whatever trailing text could still grow into a tag is held back until the next
    chunk decides it.
    """

    def __init__(self) -> None:
        """Start outside a think block, holding nothing back."""
        self._inside = False
        self._pending = ""

    @property
    def inside(self) -> bool:
        """True when the stream ended (or paused) in the middle of a think block."""
        return self._inside

    def feed(self, text: str) -> list[tuple[str, str]]:
        """`(text, channel)` pairs for one chunk, with the tags themselves removed."""
        if not text:
            return []

        out: list[tuple[str, str]] = []
        buffer = self._pending + text
        self._pending = ""

        while buffer:
            tag = THINK_CLOSE if self._inside else THINK_OPEN
            index = buffer.lower().find(tag)
            if index < 0:
                break
            if index:
                out.append((buffer[:index], self._channel))
            buffer = buffer[index + len(tag) :]
            self._inside = not self._inside

        held = _partial_tag_length(buffer)
        if held:
            self._pending = buffer[len(buffer) - held :]
            buffer = buffer[: len(buffer) - held]
        if buffer:
            out.append((buffer, self._channel))
        return out

    @property
    def _channel(self) -> str:
        """Which channel the text being emitted right now belongs to."""
        return "thinking" if self._inside else "answer"

    def flush(self) -> list[tuple[str, str]]:
        """Whatever was held back waiting for a tag that never arrived."""
        if not self._pending:
            return []
        out = [(self._pending, self._channel)]
        self._pending = ""
        return out


def _partial_tag_length(buffer: str) -> int:
    """Length of the trailing slice that could still turn out to be a think tag."""
    lowered = buffer.lower()
    for size in range(min(len(buffer), _MAX_TAG - 1), 0, -1):
        suffix = lowered[-size:]
        if THINK_OPEN.startswith(suffix) or THINK_CLOSE.startswith(suffix):
            return size
    return 0
