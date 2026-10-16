# AGENTS.md — `consumers/tutor/` — the Socratic tutor

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
The client is `web/src/consumers/tutor/AGENTS.md`.

## `consumers/tutor/` — the Socratic tutor, beside the system it reads

Mounted like the evaluation: **`consumers.tutor` imports `variatio` and never the reverse** (the
registry's optional import is the exception); `consumers/tutor/__init__.py` never imports
`consumers/tutor/api/`, so `import consumers.tutor` stays free of FastAPI/SQLAlchemy.
`server/app.py` calls `consumers.tutor.api.install(app)`, which registers the three jobs in `HANDLERS` (never in `JOB_LABELS`,
which is what `POST /api/jobs` accepts: a turn comes through the tutor's routes or not at
all), their models in `server/jobs/lanes.EXTRA_MODELS`, and mounts `/api/tutor` and the
admin's read.

- **A chat and a card.** The interaction is a plain conversation; the advantage is the CARD
  (`consumers/tutor/card.py`) code writes for every reply from the artifacts: the focus concept with its
  definition and the graph's anchored passages, its direct prerequisites (TAKEN AS KNOWN: the
  reply neither quizzes the student on them nor steers towards them, and only tells a student
  who says one is missing to review it — decision of 2026-10-03, after a question about
  recursion was walked back through functions and procedures), its direct dependents (not to be introduced), its closest same-unit concepts
  (by description vectors), the passages of the notes nearest the message (`passages.py`), the
  subject's criteria, the bank exercise the message is and a simpler one of its concept.
  **The send-back is pointed out on the turn it may apply to** (2026-10-08): when the message
  names a prerequisite of the focus (`Card.named_before`, read by `lexicon.mentions`), the card
  says so and asks, if the student lacks it, for one sentence that names it and tells them to
  review it, never an explanation. The method's rule alone was not followed: measured on 8
  messages saying a prerequisite was missing, twice, 3 replies of 16 sent the student back
  before and 12 after; 2 messages that only name one, twice, were sent back 0 times of 4.
- **A turn** (`consumers/tutor/turn.py`): `screening.screen_message` (the guardrail alone — decision of
  2026-10-03; admissibility rules on commissions) → one query-side embedding (concepts and
  passages) and one document-side one (`classify.bank_match`) → kind → focus → card → reply →
  checks. Seven kinds (`theory exercise attempt solution social administrative off_topic`);
  the last two are fixed texts that never reach the model. Classification is signals first
  (bank match ≥ `tutor.bank_match_threshold`, a conversation opened on a generated exercise),
  then one grammar call to the classify model, failing open to `theory`; the graph overrules
  an `off_topic` verdict on a message whose best concept clears `tutor.focus_threshold`.
- **The concept map** (`consumers/tutor/concept_map.py`) is drawn by CODE, never by the model: one hop
  of the graph around a focus concept — prerequisites (`before`), dependents (`after`) and the
  other relations (`links`, with the graph's own label and direction) — capped (4/3/3, the
  closest by description vectors kept, the rest counted) and sent as data in the turn's
  `concept_map`; the client draws it as a graph of its own chips with lines traced over
  them (`web/src/consumers/tutor/ConceptMap.tsx`, no Mermaid: user's request of 2026-10-08 for a
  better look, keeping the graph's shape — every relation drawn, none written as a
  sentence) in the interface language and the palette's tokens. It is shown at TWO moments only: the first
  time the conversation stands on a concept (one per move of the focus; the card says so,
  `map_of`), and when a reply sends the student back to a prerequisite (`Card.sent_back`: one
  sentence names the prerequisite AND tells the student to go over it, the prompt set's
  `REVIEW_PATTERN`), with
  that prerequisite marked — once per prerequisite and never within `REVIEW_GAP` (2) replies
  of another map. A concept with nothing before or after it has no map. The state keeps
  `mapped` and `since_map`. A reply with a ```mermaid fence of its own fails the `diagram`
  check.
- **Formulas are the model's**: the system prompt lets a reply write notation between dollar
  signs (KaTeX draws it), only where it is clearer than the sentence it replaces and never as
  the result the student has to find. No check counts them.
- **The focus belongs to the conversation**: set by a message whose best concept clears
  `tutor.focus_threshold` (0.55, measured: content questions 0.61–0.66, a greeting 0.49) and
  moved only past `tutor.focus_margin`, and NEVER to a concept in the prerequisite closure of
  the current focus (a student answering about functions inside a conversation on recursion is
  still on recursion), nor when the message names a concept of that closure but not the
  best-scoring one («¿qué es un registro?» scored «Campo», the record's neighbour, above the
  record); a second concept is never one of the closure either. Social messages never move it. **The student may choose it**: a message
  may carry one `concept` (validated against the graph, never a generic one; stored on the
  student's turn, never on the job), and then nothing is deduced — the chosen concept leads
  (`focus.with_chosen`), joined by the message's own best concept when that clears the
  threshold and is not a prerequisite of it; a `social`/`off_topic` verdict for such a
  message is answered as theory (`decided_by: "chosen"`), an administrative one stays.
  `GET /api/tutor/syllabus` (`auth.VIEW`) lists the units and their non-generic concepts. The state is the focus and the trail;
  older records may still carry a `verified` list, which nothing reads.
- **The method is code, not only prompt.** `consumers/tutor/checks.py` verifies what a machine can: at
  least one question and at most `max_questions`, at most `max_code_lines` in fences, no name
  of the student's exercise in its code that the card's notes do not use (`code_specific`,
  2026-10-15, a colleague's rule: a generic fragment of how a construct is used yes, code the
  student takes to the exercise by changing one name no; a line quoted from the student's own
  code is skipped, names of three characters at least, no language named — its vocabulary is
  the notes'; the method's code rule says the same, «lo mejor es no dar código»; unmeasured,
  as the engine was down), no run
  longer than `copy_max_words` copied from the card's passages, no sending the student to the
  notes or naming a place of them (`pointed`, the prompt set's `POINTING_PATTERN`), no
  dependent of the focus the student did not bring up, no forbidden term (in code ever, in prose when unprompted), no
  sentence opening by telling the student they are right (`VALIDATION_PATTERN`), not empty,
  not cut. A failure is retried ONCE with a note naming it; a second failure sends a fixed
  question built from the card. Replies are shown whole, never streamed.
- **Criteria are an artifact of their own**: `artifacts/tutor_criteria_autogenerated.json`
  (the `tutor_criteria` job: one grammar call per KG domain over its normative paragraphs —
  `NORMATIVE_PATTERN` first — its anchored passages and up to `criteria_solutions` bank
  solutions; every criterion must cite an id it was given or it is dropped; subject-wide ones
  are merged by one grouping call, read as a partition; each call is capped by
  `criteria_per_unit` (5) as the grammar's `maxItems` and by `criteria_max_tokens` — uncapped,
  the grammar let the model add criteria for minutes; each criterion is one plain sentence of
  20 words at most with at most three concepts — the first draft was long sentences tied to
  four or five concepts and eight sources, and unreadable; a forbidden term is a name as code
  writes it, three words at most — the model wrote practices there, which no check can find) and
  `artifacts/tutor_criteria.json`
  (a teacher's correction, which wins). A rebuild retires the curated file to `.history/`.
  `criteria.normalize` is the one cleaner of both, validated against the graph on read. The
  method's rules (`prompts.METHOD_RULES`) are one list numbered into the system prompt and
  live there alone: no route returns them and no screen lists them (the screens describe the
  tutor in prose). Criteria routes are `auth.EDIT`: the membership role, never
  `users.evaluator_profile`, which authorises nothing inside a subject.
- **Grammar**: `calls.grammar_for` drops it when the call reasons or the model is remote
  (Cerebras mangles non-ASCII under constrained decoding); the schema then goes in the prompt.
- **Passages** are cut by SECTION from the page cache (`split_sections`, long ones by
  paragraph), never packed across units, navigation and heading-only pieces dropped, no model
  call; cached in `cache/embeddings/tutor_passages.npz` by fingerprint (model, prefix, cut,
  text), held per slug in memory and rebuilt when a page changes.
- **Conversations** are files, `<workspace>/tutor/user_<id>/<id>.json`, private to their
  author (the same 404 for others' and malformed ids); the installation administrator reads
  every account's, read-only, at `/api/admin/workspaces/{slug}/tutor`. A subject's teachers
  read what their students asked as figures and a weekly digest in paraphrase, never a
  conversation (`consumers/tutor/api/activity.read`, `consumers/tutor/digest.py`; see *Class activity* in `server/AGENTS.md`). Every
  reply keeps `sent_back` — the concept and the prerequisite it sent the student back to, or
  null — which the weekly counts read; an older turn says it only through its map's `review`. A file is written whole
  under a per-file lock; the job reads it under that lock too (the route holds it until
  `pending` is written — a free lane started the job before that). `pending` names the job;
  a job gone (failed, cancelled while queued, lost to a restart) marks the student turn
  `failed` and frees the conversation; «Pedir la respuesta otra vez» is `/retry`. A
  conversation starts titled by its first line; the first reply of a substantive kind (not
  social, blocked or a fixed text) asks the classify model for a short title once
  (`consumers/tutor/title.py`), written with that reply (`titled: true`); a failure keeps the old title.
- **The tutor speaks for itself** (user's decision of 2026-10-08): the card is what the tutor
  KNOWS, not what it cites. Its labels name no source («Definición», «Lo que sabes de él»,
  «Otras cosas que sabes»: with «En los apuntes» and then «Lo que el material dice» the
  replies wrote «en los apuntes…» and «el material indica…»), and the method tells the reply
  to lean on what it knows and say it in its own words, sending the student nowhere — no
  notes, unit, section or document — and never saying where it comes from. The copy check
  still forbids pasting it; `pointed` refuses the pointing. A send-back to a prerequisite
  names the concept and the verb alone («repasa qué es…», `REVIEW_PATTERN`). Nothing is
  drawn under a reply but its map, and the tutor serves no document: a student who wants the
  notes looks for them on their own. Measured on a script of 20 messages in two subjects:
  18 replies of 20 named «apuntes» before, none after.
- `tutor.message_max_chars` (12 000) is a hidden safety cap, never shown as a counter.
- **A daily limit per account** (`tutor.daily_messages`, empty = none): counted in the
  database (`tutor_usage`, by UTC day) across every workspace, because the queue is the
  installation's and a count of files could be reset by deleting a conversation. Only a turn
  that enters the queue counts, a reply asked again included. The refusal is a 429 with
  `X-Error-Code: tutor_daily_limit`, `Retry-After` and the wait in words. The client builds
  its own sentence from the code and `Retry-After` (`consumers/tutor/limit.ts`; the server's only
  without the header) and shows it alone where the conversation reports a failure, never
  under «No se pudo enviar»; the next send or retry clears it.
- **A conversation may open on an exercise** (`opened_from`): a generated one of the author's
  (`generation_id`) or, since 2026-10-14, one of the bank this account reads (`bank_id`,
  refused like a missing one when hidden from it; `opened_from` keeps `bank_id`, the content
  `key` that survives a re-extraction, its concepts — the primary first — and its type), so a
  reading per exercise is possible later. Either gives the turn its concepts as the focus.
- **A turn's job carries no text**: params and result name the conversation and the turn
  only, because a job is read where its conversation is not (the panel's queue) and a
  conversation is its author's; its events reach its author alone
  (`PRIVATE_KINDS`). One reply on its way per conversation and per account in the workspace
  (409).
- The store of conversations, the daily count, the quiet stream of a turn's job and the
  routes' common half are the free chat's too, kept once in `server/conversations/` (see
  its `AGENTS.md`); `consumers/tutor/api/store.py` and `usage.py` bind them to the tutor's folder, role
  (`tutor`), initial state (`focus`, `trail`) and limit (`tutor_daily_limit`). The files did
  not move.
- Logs in Spanish with `[tutor]`; never the message text.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

**Tutor**
- D-195 — As many doors after the construction as functions open to the account.
- D-197 — The tutor's replies wait in the queue like any job and say «en cola»; shown whole,
  after the checks, never streamed.
- D-198, D-199 — Conversations are private to their author; the administrator reads them
  read-only; teachers read figures and a weekly paraphrased digest they ask for, never a
  sentence, a name or a conversation; students are not told.
- D-201, D-202 — Criteria are generated and curated by a teacher; a student never sees them.
  The method's rules are fixed and live in the prompt alone.
- D-203 — What the syllabus places before the concept asked about is taken as known; the focus
  never moves back to it.
- D-204 — A student may choose ONE concept for a message; optional; units are never chosen.
- D-205, D-206 — Concept maps are drawn by code from the graph, sparingly; the model draws
  none. Formulas are the model's, between dollar signs.
- D-207 — A reply tells the material in its own words and sends the student nowhere; no reader
  in the tutor.
- D-210, D-211 — One typeface (Archivo); the two voices differ by material and side. The map is
  the app's chips with traced lines, every relation drawn, no unit on the concept.
- D-213 — The tutor screens with the guardrail alone, not admissibility.
- D-214 — A bank exercise's solution never enters the card.
- D-215 — No "System One" classifier: the kind is decided by signals and one grammar call.
