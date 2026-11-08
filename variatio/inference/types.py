"""The vocabulary every engine and every caller of the boundary shares: answers, sampling, errors."""

from collections.abc import Callable
from dataclasses import dataclass

TokenSink = Callable[[str, str], None]
ProgressSink = Callable[[int, int], None]


class InferenceError(Exception):
    """Anything the engine could not do, phrased for the panel rather than for a log."""


@dataclass
class GenerationResponse:
    """One answer, with the model's deliberation kept out of it.

    `truncated` says the engine stopped for want of output budget rather than because the
    model finished — Ollama's `done_reason == "length"`, Cerebras' `finish_reason ==
    "length"`. It is the engine's own reading and not a heuristic, which is what lets a
    caller treat a cut answer as a failure instead of as a short one.

    `loop` is the unit the answer was repeating when the engine stopped reading it — set
    only for a caller that asked with `stop_on_loop`, and the reason `response` ends where
    it does: what the model wrote up to the loop is there, the repetitions are not.
    """

    response: str
    thinking: str | None = None
    truncated: bool = False
    loop: str | None = None


@dataclass(frozen=True)
class Sampling:
    """How the engine draws each token: a temperature, and a top-k and top-p when set.

    An empty top-k or top-p is not sent, and the model's own value decides — its Modelfile
    on Ollama, the provider's default on Cerebras.
    """

    temperature: float
    top_k: int | None = None
    top_p: float | None = None
