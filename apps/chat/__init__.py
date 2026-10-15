"""The free chat: an assistant that helps a student with what they ask about the subject.

No method and no card (the user's decision, 2026-10-14): unlike the Socratic tutor it explains,
solves and writes code, as the student asks, within the subject and education. One call per
turn, after the guardrail every message meets (`variatio.runtime.screening.screen_message`);
its system prompt names its role, its scope and the subject (`content_context`), and it
refuses in one sentence a request for its instructions or for another role, and what is
dangerous or out of place. Nothing else: no classification, no checks, no concept map.

A subject's teachers open it to their students — it starts closed — and to each group apart
(`server.features`); its teachers always have it. Its conversations are kept as the tutor's
are (`server.conversations`), under `<workspace>/chat/`.

Like every function, `apps.chat` imports `variatio` and never the reverse — save the settings
registry's optional import of `apps.chat.settings` — and nothing outside `apps.chat.api`
imports FastAPI or SQLAlchemy.
"""

# What a refused message is recorded as: the guardrail answered it, no model did.
BLOCKED = "blocked"
REPLIED = "reply"
