# AGENTS.md — `consumers/evaluation/` — the study

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.

## `consumers/evaluation/` — the TFM's study, outside the system it measures

Always mounted. **`consumers.evaluation` imports `variatio`, never the reverse** (one exception:
the settings registry's optional import); `consumers/evaluation/__init__.py` never imports
`consumers/evaluation/api/`, so `import consumers.evaluation` stays free of FastAPI/SQLAlchemy. It is
attached in `server/app.py` (`consumers.evaluation.api.install(app)`), never from
`server/routing.py`.

- **Arms**: `naive` (commercial chain `gemini → mistral → groq`, no `response_format`, no
  retries — the chain is the retry; provider and model id are stored per session), `rag`
  (retrieves 3 + 3 chunks over the RAW documents read with a plain extractor — `pypdf`,
  python-docx/pptx — never the pipeline's transcription, the bank, the profile's prose or the
  graph; gets the naive prompt plus the bare output schema), and `system`.
- Both baselines receive `content_context.prompt_block()` under the three facts.
- **A session is two cards: the system's and one rival** (`naive` or `rag`) drawn by the seed
  in `draw_session` (rival, order, `think`). Only the two drawn arms are generated.
  Three-card sessions recorded earlier are read, never rewritten.
- **One scenario per session**: drawn once by a short call and placed in both prompts, unless
  the free text already fixes a theme (`SCENARIO_NONE`). No scenario field on the form.
- The two local arms are written by `evaluation.local_model` (admin setting; null = the first
  offered generation model); no request carries a model for `evaluate`.
- After all arms, `_tag` tags every proposal; `off_limits` = tagged ∩ forbidden ∪ lexical
  mentions, drawn on every revealed card.
- **Everything blind is collected before the reveal**: per-card triage (`yes/partly/no`,
  stored by position), forced choice, decline (never a preference), then reveal, then the
  optional four-scale rubric about the system's exercise. The evaluator never sees aggregate
  scores. Time-on-task is recorded, never shown.
- Assignment of sets to evaluators by hand from the admin panel, each copy with a fresh
  shuffle; cross evaluation is behind `CROSS_EVALUATION` (off).
- Statistics are stdlib math: pairwise duels (exact binomial, Wilson), position bias on two
  positions (df 1), and **Scott's π** (not Cohen's κ) over evaluator pairs sharing a set.
- **Every fixed route is declared above `/evaluations/{session_id}`** (FastAPI matches in
  order); `test_route_order.py` checks every router.
- `consumers/evaluation/api/instruments.py` and `stage_instruments.py` are the single homes of what is
  asked. The **stage questionnaire** (one per construction step, keyed by artifact hash
  resolved server-side, `stage_evaluations`) is a Likert form: five statements on shared axes
  (`precision`, `recall`, `function`, `effort`, `overall`), 1-5 agreement, 5 is best,
  `VERSION = "4"`; earlier wordings are never pooled. `curated` records whether the answerer
  corrected the stage (nullable, only climbs). «Opened» is stamped when the form unfolds.
- The evaluation's «Analíticas» in «Administración → Funciones», between who may use it and
  its settings, filters
  by profile → account → workspace, one «Por evaluador» table, then «Fase de construcción» and
  «Fase de pruebas» blocks with CSVs; an evaluator's records can be withdrawn
  (`DELETE /api/admin/evaluations/records`).
- **The memoria must record** which engine, prompt language, first offered model, instrument
  version and arm configuration produced each result; there is no version column, so change
  dates are boundaries.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

- D-111, D-112 — The evaluator never sees the score; blind instruments come before the reveal.
- D-113 — A session shows the system's proposal and one seed-drawn rival.
