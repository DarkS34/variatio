# AGENTS.md — `server/pipeline/` — the chain of the three steps

Read the root `AGENTS.md` and `server/AGENTS.md` first. The closed decisions are numbered in
the root `DECISIONS.md`.

What is approved and what each artifact depends on (`approvals.py`), the one writer of an
artifact's files (`storage.py`), the label review's record (`taggability.py`), the subject's
context (`context_edit.py`), what a job chains (`chain.py`), what must be settled before a job
runs (`gates.py`), the chain as the bar reads it (`view.py`), the construction's job kinds
(`jobs.py`) and the routes of `/api/pipeline` and `/api/context` (`routes/`).

- **The construction's jobs register at `jobs.install()`**, which `server/app.py` calls as it
  installs each function. A test that runs one of these kinds without making the app calls
  `install()` itself. The jobs and the routes are leaves of the server's layers: nothing
  imports them but `app.py` and `routing.py`.

## Build chain and approvals

- `approvals.ARTIFACTS` order: graph → profile → bank (2026-10-08; it led with the profile).
  The graph comes first because the bank is tagged with it; the profile and the bank are the
  two parts of ONE step, the types first. `GATES` answers «are X's upstreams approved?»;
  `NEEDS_APPROVED` gates `review_taggability` on the profile.
- A build writes exactly one artifact (+ its cache). `chain.py` holds two chains,
  each link with its own condition, an unmet one a skip with its reason logged, never a
  failure: the graph build chains describing its concepts (the graph exists), and the
  taggability review heads the BANK's collection — `review_taggability → build_bank → index`
  (the profile and the graph approved and a document in the exemplars' slot; a profile and
  a bank). «Recoger el banco» queues the head; the pipeline's `build_job` of the bank is
  `review_taggability`. The graph no longer chains the review or the index: indexing between
  a graph build and a bank collection embedded concepts nobody had reviewed.
- **The bank's collection closes the bank** (`chain.CLOSES`, the user's decision of
  2026-10-08): when the last link that ran after the head ends the chain, the bank is
  approved and `pipeline.changed` published, so step 3 reads done and the doors open as soon
  as the bank is extracted, tagged and indexed. Only behind types and a syllabus still
  approved (`gate_open`): types corrected while it ran leave the bank a draft. Links carry
  their head in `params.head`; a job outside a chain closes nothing. A retag (`tag`) seals a
  closed bank again (`handle_tag`, like the review's reseal), and so does a hand edit of its
  exercises (see below).
- **The route checks every link of a chain** before queueing its head
  (`gates.gate_error`, `transcribing_slot`, both over `chain.links(kind)`): a link the
  runner queues has no route, so a closed gate behind the head would be skipped in silence
  and a transcription of the exercises would collide with the build behind the review.
- **The bank reads as building from its review on** (`singletons.building`: a live
  `review_taggability` whose chain names `build_bank`), and the runner queues a job's next
  link BEFORE announcing the job finished (`runner._execute`), so no reading between the two
  finds the chain gone and offers to collect again.
- **The review is skipped when nothing it reads changed** (`taggability.py`): a
  fingerprint of the profile's bytes, the graph's units and concepts in their order and the
  context's bytes — NOT the non-taggable list, which is what a teacher corrects by hand, and
  not the bank —, kept in `cache/taggability_review.json` (a cache: a graph that says
  `taggability_reviewed` with no record is taken at its word and the record written; emptying
  the graph's stage deletes it, `approvals.DERIVED`). Skipped, the job answers
  `{"skipped": true, …}` with no model call, and a switch turned by hand survives the next
  collection. **The review seals the graph's approval again** (`kg_edit.set_non_taggable(…,
  reseal=True)` when the graph was approved, `Approvals.sealed`): it is the system's
  derivation, not a teacher's edit; a hand edit of the switch still withdraws it.
- **The raw documents are an upstream**: `jobs._build` records the slot's documents
  (name, size, mtime) in `artifacts/.built_from.json`; a stage built from documents its slot no
  longer holds is stale with the drift named, and offers «Volver a construir» (the only
  rebuild offered anywhere). `approvals.RAW_SOURCE` is the one table of which slot feeds which
  artifact. A stage with no record is never stale for its documents.
- **A build waits for a LIVE transcription of the slot it reads** (409 outside `force`),
  because both write the same page cache. `singletons.transcribing(slug, slot)` is the one
  reading. This is not a gate on transcription having happened.
- Every hand edit withdraws the stage's approval on the server; the client never reopens.
  **One exception: an exercise of a closed bank** (the user's decision, 2026-10-14). Editing,
  retagging, adding or deleting one seals the bank again (`bank_edit._persist`) when it was
  closed behind closed types and syllabus and stale for nothing, so a teacher correcting an
  erratum mid-course does not close generating and the tutor to the class. A draft stays a
  draft; editing the types still withdraws them and closes the doors.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in the root
`DECISIONS.md`. Do not reverse one without the user's explicit request.

- D-017, D-018 — A build writes only its final artifact; draft and curated stay two files. The
  bank's building file is the one exception.
- D-019, D-020, D-022, D-023 — Taggability is not part of the builder: it heads the bank's
  collection (`review_taggability → build_bank → index`), is skipped when the profile, the
  syllabus and the context did not change, and seals the graph's approval again; no `GATES` or
  `JOB_ARTIFACT` entry. The route checks the gates of every link before queueing a head.
