"""The Socratic tutor: a conversation that guides a student through the subject's own materials.

A chat as plain as the custom GPTs it replaces — a message in, a reply out — with one
difference that is the whole point: every turn carries a CARD that code writes from the
workspace's artifacts (the graph, its anchored passages, the notes, the bank, the profile and
the subject's criteria), so the model is told where in the notes the answer lives, what the
student is assumed to know and what comes later, instead of searching blind.

Two layers of rules, never mixed. The METHOD is the system's and holds in every subject: it
lives in `tutor.prompts` and in the deterministic `checks`, and no file can switch it off.
The CRITERIA are the subject's: drafted from the artifacts and curated by a teacher
(`tutor.criteria`).

The boundary is pinned as the evaluation's was: `tutor` imports `variatio` and never the
reverse — save the settings registry's optional import of `tutor.settings` — and nothing
outside `tutor.api` imports FastAPI or SQLAlchemy, so `import tutor` stays a library.
"""

# What a student's message can be, which decides the card a turn is answered with. The two
# last ones are answered by code with a fixed text and never reach the reply model.
THEORY = "theory"
EXERCISE = "exercise"
ATTEMPT = "attempt"
SOLUTION = "solution"
SOCIAL = "social"
ADMINISTRATIVE = "administrative"
OFF_TOPIC = "off_topic"

KINDS: tuple[str, ...] = (THEORY, EXERCISE, ATTEMPT, SOLUTION, SOCIAL, ADMINISTRATIVE, OFF_TOPIC)
FIXED_KINDS: frozenset[str] = frozenset({ADMINISTRATIVE, OFF_TOPIC})

# A message the guardrail refused. Not a kind the classifier can answer: the guardrail runs
# first and the message reaches nothing else.
BLOCKED = "blocked"

__all__ = [
    "ADMINISTRATIVE",
    "ATTEMPT",
    "BLOCKED",
    "EXERCISE",
    "FIXED_KINDS",
    "KINDS",
    "OFF_TOPIC",
    "SOCIAL",
    "SOLUTION",
    "THEORY",
]
