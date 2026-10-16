# AGENTS.md — `consumers/chat/` — the free chat

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.

## `consumers/chat/` — «Chat libre»

An assistant without the tutor's method (the user's decision, 2026-10-14): it explains,
solves and writes code, as the student asks, within the subject and education.

- **A turn** (`consumers/chat/turn.py`): the guardrail (`screening.screen_message`; a refusal is a
  fixed text, kind `blocked`, and reaches no model), then ONE call (`chat_reply`) with the
  system prompt — its role, its scope, refusing in one sentence a request for its
  instructions or another role and what is dangerous or out of place, and the subject's
  `content_context.prompt_block()` — the last `chat.history_turns` exchanges and, when the
  conversation was opened on an exercise, that exercise. No classification, no card, no
  checks, no map. Its job (`chat_turn`) needs no runtime context: it never warms a subject's
  embedder or graph.
- **The model**: `chat.models.reply`, empty = `VARIANT_GENERATION_LLM` (the generation's, the
  user's choice; the tutor falls back to the same); its reasoning switch and effort, its
  sampling triple, `chat.reply_max_tokens` (2048), `chat.message_max_chars`,
  `chat.daily_messages` (empty = none; counted apart from the tutor's, `chat_daily_limit`).
  Declared in `consumers/chat/settings.py` (stage `chat`, after the tutor's; `MODEL_KEYS` join
  `registry.EXTRA_MODEL_KEYS`), picked up by the registry's optional import, and drawn in
  «Configuración» — it is no optional function of the administrator's.
- **Who uses it**: a subject's switch, `workspaces.student_chat` (migration 0023), CLOSED by
  default, and the group's (`class_groups.chat`); its teachers always have it
  (`features.CHAT`, `auth.CHAT` on its router; `/api/auth/me`'s `features.chat`). The job is
  class A, private and a student's kind.
- **Its routes** (`/api/chat`, `auth.VIEW` + `auth.CHAT`): one's conversations, open (with a
  `generation_id` of one's own or a `bank_id` one reads), read, send, ask again, stop, delete
  — the tutor's, through `server/conversations/routes`. An exercise is checked before the
  queue, and `opened_from.exercise` keeps it as labels and texts: every field of one's own
  generated exercise, only the fields shown of the bank's (the level always) — a hidden field
  never reaches the model.
- **The class's week** counts its messages by student and day (`activity.CHAT_READER`,
  `ChatMessage`): the week's `chat` block, `chat_days`/`chat_messages` per row, `chat` in the
  strip, the median, and the `chat` area's `idle`/`trend`/`quiet` findings. Nothing of what a
  message was about.
- Its client is `web/src/consumers/chat/` (`ChatScreen`: the tutor's layout — the list beside the
  conversation, the two voices, the box — without the map, the question set apart or the
  concept picker), its strings in core (`chat.*`). «Llevar al chat libre» (`lib/chatDraft.ts`)
  on a saved result, a card of «Mis ejercicios», and the rows of a student's bank and
  generated exercises, each where the chat is open.
- Logs in Spanish with `[chat]`; never the message text.
