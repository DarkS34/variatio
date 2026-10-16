# Decisions

The register of the closed decisions of Variatio: the rules that must not be undone without
the user's explicit request, each with the reason it was taken. `AGENTS.md` carries each rule
in force in one line with its number; this file carries the date, the commit, the reason and
what each decision replaced.

## How to read an entry

- **Number** (`D-001`…): stable. A number is never reused or renumbered.
- **Rule**: what holds, in the present tense.
- **Date**: when the decision was taken; the commit may be a day later.
- **Commit**: the commit that introduced the rule's behaviour (found with `git log -S`).
  `(first recorded)` marks the first commit where the rule appears in writing when no earlier
  commit introduces it; the behaviour may be older. Before `98bf7d4` (2026-10-01) the rules
  lived in an untracked file, so many entries point to code commits instead.
- **Status**:
  - `in force`;
  - `superseded by D-NNN`: the earlier rule, kept so the history is readable;
  - `in force until D-NNN applies`: a later decision is taken but its phase is not done;
  - `decided; applies in plan phase Fn`: taken on 2026-10-16 with the refactor plan, not yet
    in the code.
- **Why**: the reason, from the commit, the user's words or a measurement. `Not recorded.`
  means that no commit or note gives one.

## How to change a decision

1. Ask the user first. A closed decision changes only on the user's explicit request.
2. Add a new entry with the next free number. Do not edit the rule of an old entry.
3. Mark the old entry `superseded by` the new one.
4. Change the rule's line in `AGENTS.md` in the same commit as the code.

## Structure

### D-001. Code licensed PolyForm Noncommercial
- **Rule:** The code is under the PolyForm Noncommercial License 1.0.0 (1.171.0 on `main`, 3.4.0 on `variatio-vanilla`): free for any noncommercial use, never sold.
- **Date:** 2026-10-11 · **Commit:** `ae4d2f7` · **Status:** in force
- **Why:** The user's decision: free for noncommercial use (study, research, educational and public bodies) and no commercial use licensed.

### D-002. Code licensed MIT
- **Rule:** The code is under the MIT license, declared in `LICENSE`, `pyproject.toml` and `web/package.json`.
- **Date:** 2026-09-21 · **Commit:** `3bed8de` · **Status:** superseded by D-001
- **Why:** Not recorded.

### D-003. MIT history is not rewritten
- **Rule:** The history is not rewritten to hide the MIT commits, and copies taken while the code was MIT keep MIT.
- **Date:** 2026-10-11 · **Commit:** `ae4d2f7` · **Status:** in force
- **Why:** Copies were cloned while the code was MIT, and a rewrite would not take that licence back from them.

### D-004. Functions live in consumers
- **Rule:** The functions the system is used through live in `consumers/`, outside `variatio/` and `server/`, with a one-way import; the evaluation is not made removable. `consumers/` holds functions on the artifacts alone.
- **Date:** 2026-10-16 · **Commit:** `8c717f6` · **Status:** in force
- **Why:** The functions consume the artifacts the construction produces, and the directory now says so (the user's request).

### D-005. Functions grouped under apps
- **Rule:** Generation, evaluation and tutor live under one package `apps/`, each with its own `install(app)`, with one-way imports pinned by a boundary test.
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** superseded by D-004
- **Why:** The user's request to group the functions in one directory.

### D-006. Evaluation as top-level package outside library
- **Rule:** The evaluation is a top-level package (`study/`, later `evaluation/`) outside the library; it imports the library and never the reverse, and it is not made removable.
- **Date:** 2026-08-23 · **Commit:** `f7ff263` · **Status:** superseded by D-005
- **Why:** The dependency was already one-way (no pipeline module imported the arms); the move made it positional.

### D-007. Shared conversations live in server
- **Rule:** What the tutor and the chat share (store, daily count, quiet emitter, route half) is `server/conversations/`, not a package of `consumers/`.
- **Date:** 2026-10-16 · **Commit:** `f34dd5e` · **Status:** in force
- **Why:** It is no function (no route, job, setting or `install(app)`) and imports `server` and `variatio`, never the functions (the user's decision).

### D-008. Library split into builders, runtime, entrypoints
- **Rule:** The library is split into `builders/`, `runtime/` and `entrypoints/`, and the package root holds three files only (`config.py`, `cli.py`, `__init__.py`).
- **Date:** 2026-09-06 · **Commit:** `8bdc568` · **Status:** in force
- **Why:** Loose root files that run when an exercise is asked for had no home; `builders` against `runtime` is the authoring/execution split.

### D-009. Renames keep keys and use per-importer edits
- **Rule:** Setting keys (e.g. `models.phases.concept_tagger`) and on-disk names (`.review_state.json`) do not follow module renames. Renames are done per importer, never with a global `sed`.
- **Date:** 2026-09-06 · **Commit:** `8bdc568` · **Status:** in force
- **Why:** Renaming a key would silently reset an installation's model choice; a global sed breaks because `settings`, `review`, `runtime` and `models` each name a second live module.

### D-010. No default workspace
- **Rule:** There is no default workspace and no reserved slug; a path is never a defaulted argument.
- **Date:** 2026-08-26 · **Commit:** `7bdd240` · **Status:** in force
- **Why:** A component built without paths wrote into the default workspace while serving another instance; falling into the first workspace enters somebody else's instance.

### D-011. Artifacts directory and loaders package names
- **Rule:** A workspace's artifacts live in `artifacts/` and their loaders in `variatio/loaders/`; this renaming is its own, not one that followed a module's, and an old tree is renamed the first time it is opened.
- **Date:** 2026-10-08 · **Commit:** `73b8611` · **Status:** in force
- **Why:** «instance» did not say what the directory held and also named the loaders' package and the whole subject (the user's decision).

### D-012. Artifacts and loaders both named instance
- **Rule:** A workspace's artifacts live in `instance/` and their loaders in the package `instance/`.
- **Date:** 2026-08-23 · **Commit:** `8d99cc8` · **Status:** superseded by D-011
- **Why:** The loaders were grouped as the readers of what `workspaces/<slug>/instance/` holds.

### D-013. Settings in registry and config.json
- **Rule:** Settings are declared in the registry and stored in `config.json`, with one writer (`store.write_file` → `json_io`).
- **Date:** 2026-08-22 · **Commit:** `5915b9a` · **Status:** in force
- **Why:** Each setting carries the measured prose that justifies it; `config.py` becomes an index of bare annotations.

### D-014. Dotenv loader in core
- **Rule:** The dotenv loader lives in `core/dotenv.py`, not in `config`.
- **Date:** 2026-08-22 · **Commit:** `a764e98` · **Status:** in force
- **Why:** Not recorded.

### D-015. One writer of persisted JSON
- **Rule:** Every persisted JSON file is written by `json_io.write_json`.
- **Date:** 2026-08-18 · **Commit:** `431e114` · **Status:** in force
- **Why:** Approval hashes are hashes of these bytes, so six drifting copies of the writer would make approvals look outdated.

### D-016. Knowledge-graph extraction in this repo
- **Rule:** Knowledge-graph extraction lives in this repo with no `kg-builder` dependency, and the web app is the only graph viewer.
- **Date:** 2026-08-07 · **Commit:** `16c50ae` · **Status:** in force
- **Why:** Porting the pipeline dropped the external dependency and its duplicated inference, documents, JSON and config layers.

### D-017. A build writes only its final artifact
- **Rule:** A build writes only its final artifact; the draft and the curated file stay two files.
- **Date:** 2026-08-18 · **Commit:** `4d117cd` (first recorded) · **Status:** in force
- **Why:** Not recorded.

### D-018. Bank building file is the exception
- **Rule:** The bank's build checkpoints per document into `.exemplars_bank.building.json` and writes `exemplars_bank.json` once at the end; this working file is the one exception to D-017.
- **Date:** 2026-08-29 · **Commit:** `a35b4ec` · **Status:** in force
- **Why:** Re-extracting stacked a second copy of every item; a build that starts empty keeps the old bank until it finishes and signals a build in flight.

### D-019. Taggability is not part of the builder
- **Rule:** The taggability review is not part of the knowledge-graph builder; it is a job of its own, with no `GATES` or `JOB_ARTIFACT` entry.
- **Date:** 2026-08-19 · **Commit:** `f9b678d` · **Status:** in force
- **Why:** It reads the profile's modalities and real bank items, and the graph has no upstreams.

### D-020. Taggability heads the bank's collection
- **Rule:** The taggability review heads the bank's collection at the job layer (`review_taggability → build_bank → index`).
- **Date:** 2026-10-08 · **Commit:** `5dd6f74` · **Status:** in force
- **Why:** Deciding the labels needs the types closed; indexing between a graph build and a bank collection embedded concepts nobody had reviewed.

### D-021. Graph build chains the taggability review
- **Rule:** The graph build chains what it leaves pending: describe, review taggability, index.
- **Date:** 2026-08-22 · **Commit:** `0a82c76` · **Status:** superseded by D-020
- **Why:** A finished build left work owed behind buttons on two screens that had to be pressed in order.

### D-022. Review skipped when inputs unchanged
- **Rule:** The review is skipped when the profile, the syllabus and the context did not change, and it seals the graph's approval again.
- **Date:** 2026-10-08 · **Commit:** `5dd6f74` · **Status:** in force
- **Why:** A switch turned by hand survives the next collection; the review is the system's derivation, not a teacher's edit.

### D-023. Route checks every link's gates
- **Rule:** The route checks the gates of every link of a chain before queueing the chain's head.
- **Date:** 2026-10-08 · **Commit:** `5dd6f74` · **Status:** in force
- **Why:** A link the runner queues has no route, so a closed gate behind the head would be skipped in silence.

### D-024. Content context is its own artifact
- **Rule:** Content context is its own artifact, written by the graph and profile builders; it keeps the three named facts and the single renderer (`prompt_block()`).
- **Date:** 2026-08-22 · **Commit:** `4c18de3` · **Status:** in force
- **Why:** It was not a property of the profile, and a graph build writes one artifact so could not write into the profile's file; five copies of the renderer fixed its shape.

### D-025. Transcription is an accelerator, not a gate
- **Rule:** Transcription is an accelerator and a step of `/raw`, never a gate for a build nor a stage.
- **Date:** 2026-08-27 · **Commit:** `791662f` · **Status:** in force
- **Why:** Every builder keeps its own conversion phase; trading a wait for a wall would be the worse bargain.

### D-026. Step 1 done with every document read
- **Rule:** Step 1 reads done only with both origins stocked and every document read.
- **Date:** 2026-10-12 · **Commit:** `322e682` · **Status:** in force
- **Why:** The bar said «Hecho» over a screen whose one coral control was still «Procesarlos todos ahora» (the user's decision).

### D-027. Step 1 done with documents in both origins
- **Rule:** Step 1 reads done as soon as both origins hold a document, read or not.
- **Date:** 2026-08-31 · **Commit:** `c3dec33` · **Status:** superseded by D-026
- **Why:** The raw material became step 1 of the bar because uploading the notes is the first thing a teacher does.

### D-028. Both raw slots use the VLM page route
- **Rule:** Both raw slots are transcribed through the same VLM page route, one model call per page.
- **Date:** 2026-08-27 · **Commit:** `017fae0` · **Status:** in force
- **Why:** Quality outweighs speed: one algorithm and one place to review what came out.

### D-029. No PDF to DOCX conversion
- **Rule:** Documents are not converted from PDF to DOCX.
- **Date:** 2026-10-01 · **Commit:** `98bf7d4` (first recorded) · **Status:** in force
- **Why:** Not recorded.

### D-030. Office pictures read with the page model
- **Rule:** Pictures in Office files are transcribed with the page model, with no separate model setting.
- **Date:** 2026-09-02 · **Commit:** `fbcc0c4` · **Status:** in force
- **Why:** Quality over speed (user request): Docling could not read the pictures; one model per document whichever route its pieces take.

### D-031. Metafiles rasterised through LibreOffice
- **Rule:** EMF/WMF metafiles are rasterised through LibreOffice PNG export on a copy of the package.
- **Date:** 2026-09-02 · **Commit:** `fbcc0c4` · **Status:** in force
- **Why:** Pillow and Docling read neither format; measured on three reference workbooks, 0 unreadable pictures where there were 6.

### D-032. Build waits for live slot transcription
- **Rule:** A build waits for a live transcription of the slot it reads; this is a concurrency rule, not a gate.
- **Date:** 2026-09-11 · **Commit:** `485b3a7` · **Status:** in force
- **Why:** A transcription and a build of one slot both write the same page cache, and on a hybrid engine the queue does not keep them apart.

### D-033. Workspace-language strings live in wording
- **Rule:** Strings whose language must match the workspace live in `wording/`.
- **Date:** 2026-09-05 · **Commit:** `ffef620` · **Status:** in force
- **Why:** Code-composed strings were Spanish literals, so an English workspace was screened by a Spanish regex and given half-Spanish prompt blocks.

### D-034. Guardrail runs before the scope judge
- **Rule:** Screening makes two calls in a fixed order, the guardrail first and then admissibility.
- **Date:** 2026-08-23 · **Commit:** `cbb8b4e` · **Status:** in force
- **Why:** Not recorded.

### D-035. Screening is one package, one sequence
- **Rule:** Screening is one package, and the sequence of its two calls exists once (`screen_instructions`).
- **Date:** 2026-09-05 · **Commit:** `06f2dd3` · **Status:** in force
- **Why:** The pipeline and the evaluation each carried the same thirty lines of order, error sentences and owners derivation.

## Prompts and the graph

### D-036. Two interchangeable prompt sets
- **Rule:** Each workspace uses one of two prompt sets, `variatio/prompts/es/` and `variatio/prompts/en/`. The JSON keys the model emits are never translated, and the two sets keep the same modules, functions and signatures, pinned by test.
- **Date:** 2026-08-27 · **Commit:** `027d6a4` · **Status:** in force
- **Why:** The JSON keys are the grammar `schemas.py` pins and both sets share it byte for byte; the sets are interchangeable or they are two systems, so a function added to one and not the other fails the suite.

### D-037. Three separate language axes
- **Rule:** The interface language belongs to the account (`users.ui_language`), the prompt language to the workspace (`workspaces.prompt_language`, `locale.json`), and `language_of_instruction` to the corpus; they are three different axes.
- **Date:** 2026-08-27 · **Commit:** `1f399f3` · **Status:** in force
- **Why:** What a person reads and what the model is instructed in differ (someone working in Spanish may prepare an instance with English prompts); `language_of_instruction` is what the material is written in, decided by the corpus, not by a person.

### D-038. Every modality carries a difficulty
- **Rule:** Every modality carries a difficulty field on one shared ladder of rungs; only the criterion that places an exercise on each rung is the modality's own.
- **Date:** 2026-09-01 · **Commit:** `49581cc` · **Status:** in force
- **Why:** A column and a sort over a mixed bank mean nothing unless a rung is one value everywhere, and one generic criterion cannot discriminate across modalities; measured over 17 modalities, all already declared the same three rungs, but the criteria were generic Bloom vocabulary.

### D-039. Prompt legislates the criterion's rung shape
- **Rule:** The prompt legislates the criterion's shape: an opening sentence naming the axis, then every rung opened by `«rung»:` with a signal, an example from the modality's exemplars and its border with the neighbour rung.
- **Date:** 2026-09-01 · **Commit:** `bb8856f` · **Status:** in force
- **Why:** The criterion is now read by whoever chooses the rung in a commission, and «basico (reconocimiento)» tells them nothing; the shape lets `lib/difficulty.ts` split it per rung.

### D-040. Generation guidance is hand-written only
- **Rule:** `guidance.generation` is never generated; the modality's `general_generation_rules` carry how an item is written, and `guidance.generation` is a hand-written exception for one field.
- **Date:** 2026-08-22 · **Commit:** `54496b5` · **Status:** in force
- **Why:** The consolidator emitted both per-field generation guidance and per-modality rules, and they said the same thing (three of four rules of one modality restated a field's guidance).

### D-041. Prerequisite lists are curriculum-bounded closures
- **Rule:** Prerequisite lists are transitive closures bounded by the curriculum with opposite set operations: `assumed_known()` intersects the prerequisite closure with the curriculum and `forbidden()` subtracts it.
- **Date:** 2026-08-19 · **Commit:** `a0efd93` · **Status:** in force
- **Why:** The curriculum was ignored; the two operations differ, and subtracting on the permissive side would mark as known exactly the prerequisites the student has not seen.

### D-042. Later concepts used, not practised
- **Rule:** Without a curriculum, concepts after the target may be used but not practised (`checks.closure_rule` returns `practises`: the tagger's primary concept must not lie after the target); with a curriculum, forbidden concepts may not be mentioned.
- **Date:** 2026-09-05 · **Commit:** `7e37e1e` · **Status:** in force
- **Why:** Without a curriculum the old rule assumed everything after the target was untaught and flagged foundations falsely; measured, only 3 of 152 bank items mention something after their own primary, and teachers practise roots through later constructs.

### D-043. Course progress is a suggestion
- **Rule:** The subject's curriculum is its course's progress, set by its teachers in «Clase»; the generate form offers it in one press («Usar lo visto en clase») and it never bounds a commission, so a student may practise what the class has not covered.
- **Date:** 2026-10-07 · **Commit:** `587642a` · **Status:** in force
- **Why:** The user's decision: a student who wants to run ahead of the class may; a commission's own list replaces the progress for everybody.

### D-044. Course progress bounds a student's commission
- **Rule:** The subject's progress, set in «Clase», bounds a student's commission: their own list is cut by it, an empty list does not lift it, and a target outside it is refused with a 422.
- **Date:** 2026-10-06 · **Commit:** `e7c39fb` · **Status:** superseded by D-043
- **Why:** Not recorded.

### D-045. Curriculum is host state, no screen
- **Rule:** The subject's curriculum is a per-workspace host-state file (`.curriculum.json`) that no screen edits.
- **Date:** 2026-08-20 · **Commit:** `d83c375` · **Status:** superseded by D-044
- **Why:** Not recorded.

### D-046. Syllabus units in teaching order
- **Rule:** The units of the syllabus are written in the order they are taught: documents are read in the natural order of their names (`source_docs.name_order`), the prompt that finds the units orders them (numbering first, then the subject's logic), and code keeps that order, never sorting it back by chunk or by median position.
- **Date:** 2026-10-05 · **Commit:** `97c0726` · **Status:** in force
- **Why:** Byte order of names put «Bloque 10» before «Bloque 2» and «Copia de Tema 4» before «Tema 1», so one syllabus opened on arrays; measured on eight real outlines, such a corpus now opens on its first topic and an ordered one keeps its order.

### D-047. Units follow the material's position
- **Rule:** Domains are ordered by the median position of their members in the material (`order_domains`), and units follow the corpus chunks, with documents read in the byte order of their names.
- **Date:** 2026-08-22 · **Commit:** `546d57b` · **Status:** superseded by D-046
- **Why:** Linking reasoned over bare names in whatever order the domains were named; ordering by where the material introduces each concept made «los bloques vienen en el orden del material» true.

### D-048. One hierarchy relation
- **Rule:** The hierarchy is one relation, `se_engloba_en` («se engloba en»), read from the specific to the general.
- **Date:** 2026-08-24 · **Commit:** `0c15849` · **Status:** in force
- **Why:** The extractor could not keep `es_un` and `parte_de` apart (6 of 29 `parte_de` edges duplicated `es_un` ones) and nothing computed over the distinction.

### D-049. Related-to relation feeds embeddings
- **Rule:** `relacionado` keeps `use_in_embedding: true`, so it feeds the concept descriptions used for embeddings.
- **Date:** 2026-07-18 · **Commit:** `738c1b1` · **Status:** in force
- **Why:** Not recorded.

### D-050. Benchmark before regenerating descriptions
- **Rule:** Concept descriptions are not regenerated wholesale without benchmarking retrieval.
- **Date:** 2026-10-01 · **Commit:** `98bf7d4` (first recorded) · **Status:** in force
- **Why:** Not recorded.

### D-051. No anchoring beats a false one
- **Rule:** A concept whose name occurs in no non-navigation paragraph of its chunk gets no anchored passage; there is no «head of chunk» fallback.
- **Date:** 2026-08-19 · **Commit:** `417eb4d` · **Status:** in force
- **Why:** A concept with no anchoring is honest and the interface reports it, whereas quoting the head of the chunk anchored 43 of 200 concepts to the document's table of contents.

### D-052. Descriptions impersonal and schema-constrained
- **Rule:** Concept descriptions are written in an impersonal voice and the description call is constrained by a grammar (`DESCRIPTION_SCHEMA`).
- **Date:** 2026-08-18 · **Commit:** `1a949c5` · **Status:** in force
- **Why:** The prompt made descriptions speak as the student; and without a schema a reasoning model deliberated inside the answer, one cached description being 9 000 characters of English scratchpad embedded as prose.

### D-053. Free text is a four-slot catalogue
- **Rule:** The commission's free-text field is judged against a catalogue of four fixed slots (`ambito`, `elementos`, `extension`, `datos`) with owners derived per instance; it runs after the guardrail, the judge's answer is verified against the derived owners, and it fails open.
- **Date:** 2026-08-23 · **Commit:** `62902e3` · **Status:** in force
- **Why:** Free text is admitted only where no other control already decides the matter; failing open means a judge that cannot answer never blocks a commission, and a hard-coded owner made the model blame controls the instance did not have.

### D-054. Diagrams transcribed as Mermaid
- **Rule:** A diagram of labelled nodes and edges is transcribed as a fenced Mermaid block of the fitting type, with the surrounding text outside it; plots, plans and photographs stay `[figura: …]`.
- **Date:** 2026-09-12 · **Commit:** `12732b3` · **Status:** in force
- **Why:** An external evaluator reported class diagrams never came out and use-case ones were far from compiling; 6 of the 9 diagram exemplars of the reference bank were prose and the generator imitated them.

### D-055. Grammatical variants are one concept
- **Rule:** The graph merge treats grammatical variants of one concept as one concept: the merge prompt does not read two wordings of one definition as two concepts, and `norm_key` singularises the head of a noun phrase before `de`/`del`/`of`.
- **Date:** 2026-09-12 · **Commit:** `12732b3` · **Status:** in force
- **Why:** «Casos de uso» and «Caso de Uso» were two taggable concepts.

### D-056. One variant decision field per modality
- **Rule:** The profile may declare one `decided_by: "user"` enum per modality for a discrete variant of the deliverable (the kind of diagram, the notation, the language).
- **Date:** 2026-09-12 · **Commit:** `12732b3` · **Status:** in force
- **Why:** So a requester can ask for, e.g., a class diagram instead of always getting the most frequent kind.

## Models and inference

### D-057. Open weights, one hosted engine
- **Rule:** Only open-weight models are used; the optional `cerebras+ollama` engine is the one hosted exception and is chosen per installation. No other hosted provider is added without asking the user.
- **Date:** 2026-08-24 · **Commit:** `994516f` · **Status:** in force
- **Why:** The commit amended the earlier "open-source only / local stack" closed decision for exactly this engine, by explicit user request; everything else, guardrail and embedder included, stays on Ollama.

### D-058. No Ollama fallback on Cerebras budget
- **Rule:** When the Cerebras budget runs out, a call waits up to `CEREBRAS_MAX_WAIT_SECONDS` or is refused with a readable error; it never falls back to Ollama.
- **Date:** 2026-08-26 · **Commit:** `ca0c17f` · **Status:** in force
- **Why:** The commit set one rule for both windows: wait when relief arrives within `CEREBRAS_MAX_WAIT_SECONDS`, refuse beyond it. Why no Ollama fallback is not recorded.

### D-059. Nothing is warmed
- **Rule:** No model is warmed; `ensure_models` only checks, pulls or raises, and sends no warm-up call.
- **Date:** 2026-08-28 · **Commit:** `a82b176` · **Status:** in force
- **Why:** Eager loading saved no time (weights load on the first real call anyway) and on the hybrid profile it cost: the loop paid for loads its next iteration evicted. The early failure and one checkpoint per model (cancellable pulls) were kept.

### D-060. No main model
- **Rule:** There is no main model; every phase setting names its own model and none admits an empty value.
- **Date:** 2026-08-28 · **Commit:** `a82b176` · **Status:** in force
- **Why:** What a builder will load is read in its own setting instead of resolving through a default; `models.main`/`LLM_MAIN` and `context_window.main` were retired with `config.json` migrated so each phase resolved identically.

### D-061. Default judging and generating model
- **Rule:** The judging and generating phases default to `qwen3.8:27b-q8_0`.
- **Date:** 2026-08-29 · **Commit:** `6b84ddd` · **Status:** in force
- **Why:** Explicit user request, reversing the earlier "do not upgrade to the q8" decision: the q4_K_M was not installed on the GPU, so the local profile could not be selected. Cost accepted as measured: 19.0 vs 29.1 tok/s, 649 s vs 443 s on one curation call, 27.9 GB vs 16.5.

### D-062. Reasoning effort defaults to low
- **Rule:** A reasoning call runs at effort `low` by default; `True` is turned into a level only at the engine boundary.
- **Date:** 2026-08-18 · **Commit:** `1a949c5` · **Status:** in force
- **Why:** Measured on the A40: `medium` is the model's own default (not a rung), `high` spent 58 953 characters of deliberation and returned an empty answer, and `max` over-reasons.

### D-063. Effort max equals high on qwen3.8
- **Rule:** On `qwen3.8:27b-q8_0` the effort level `max` is treated as `high`; the model has three effective levels.
- **Date:** 2026-08-29 · **Commit:** `6faa387` · **Status:** in force
- **Why:** Measured on Ollama 0.32.13 at temperature 0 with a fixed seed: `high` and `max` render the same 56-token prompt and return a byte-identical answer, so a fourth stop changed nothing.

### D-064. Never re-add qwen3.6 q4_K_M
- **Rule:** `qwen3.6:35b-a3b-q4_K_M` is broken and is never added back to any profile.
- **Date:** 2026-08-18 · **Commit:** `1a949c5` (first recorded) · **Status:** in force
- **Why:** It fails on this machine above about 4 490 characters of prompt (an illegal memory access).

### D-065. Domain naming call without reasoning
- **Rule:** The call that names the graph's domains (`kg_domains`) runs with reasoning off.
- **Date:** 2026-08-18 · **Commit:** `1a949c5` · **Status:** in force
- **Why:** Measured: with reasoning on, the model enumerated inside the reasoning channel for 36 929 characters and returned an empty answer with `done_reason: "stop"`; with grammar and no reasoning, 56 s instead of 400 and 202 of 203 concepts placed.

### D-066. Phase context window of 65536
- **Rule:** The KV cache of every phase model is capped at 65536 tokens (`context_window.overrides`).
- **Date:** 2026-08-18 · **Commit:** `1a949c5` · **Status:** in force
- **Why:** With reasoning on, the window is prompt plus deliberation (~8 000-token prompt, ~13 000 tokens of `low` reasoning per curation call); at 65536 the judging model, guardrail and embedder still fit in 29.05 GiB of ~45. Lowering it truncates silently.

### D-067. Embedding model fixed
- **Rule:** The embedding model is fixed at `qwen3-embedding:4b` and cannot be changed from the panel.
- **Date:** 2026-08-02 · **Commit:** `9f2dfc1` · **Status:** in force
- **Why:** Measured probe of 18 queries over 14 concepts: top-1 rose from 15/18 to 18/18 against `embeddinggemma` and the right-vs-best-wrong margin more than doubled (0.069 → 0.152); the 8b was measured and discarded. The similarity threshold and query prefix are calibrated on this model.

### D-068. Cerebras ceilings are a hard cap
- **Rule:** The configured `CEREBRAS_MAX_*` ceilings are a hard cap; a response header may only lower what is believed left, never raise a ceiling.
- **Date:** 2026-08-29 · **Commit:** `115e034` · **Status:** in force
- **Why:** `remaining-*` counts against the model's quota, not the account's; reading it raised the ceilings to the catalogue's and the gate stopped holding calls (measured 91 requests in one minute and 2 832 823 tokens in a day against 5/min and 1 000 000/day configured).

### D-069. Cerebras gate books claims
- **Rule:** The Cerebras gate books a `Claim` in the flock'ed ledger before each call; `record` settles it with the exact usage, `release` returns it, and unsettled claims age out.
- **Date:** 2026-08-29 · **Commit:** `e869a24` · **Status:** in force
- **Why:** With several remote jobs at once, checking and then calling is no throttle when two callers check together, so the gate must reserve what it lets through.

### D-070. Cerebras ledger shared per account
- **Rule:** The Cerebras ledger lives outside the tree at `paths.cerebras_budget_path()` and is shared by every installation of the user; `CEREBRAS_BUDGET_PATH` is only for an installation whose key belongs to another account.
- **Date:** 2026-10-03 · **Commit:** `4b25c82` · **Status:** in force
- **Why:** Cerebras limits the organisation, not the key; with one ledger per tree, each installation of one account believed it had the whole quota. Sharing is the default because its mistake only waits longer.

### D-071. Cerebras ledger at the project root
- **Rule:** Each installation keeps its Cerebras ledger in a file at its project root (`/.cerebras_budget.json`).
- **Date:** 2026-08-26 · **Commit:** `ca0c17f` · **Status:** superseded by D-070
- **Why:** The ledger is a file because builds run out of process and are what empties a daily budget.

### D-072. No grammar for remote bank extraction
- **Rule:** With a remotely served model, the bank extraction and its repair ask without a grammar (`_grammar_costs_the_text`); the Ollama path is unchanged.
- **Date:** 2026-08-29 · **Commit:** `54f35ae` · **Status:** in force
- **Why:** Under Cerebras' constrained decoding, `gemma-4-31b` wrote every non-ASCII character as a wrong `\u00XX` escape (107 escapes in one batch, 4 distinct values); `strict=false` and `json_object` mode did not fix it.

### D-073. Commission chooses its writing model
- **Rule:** A commission chooses the model that writes the variant from the offered list `generation.models`; the name is checked at submit and in the handler, and each saved exercise records the model that wrote it.
- **Date:** 2026-08-29 · **Commit:** `961c3f5` · **Status:** in force
- **Why:** The trade-off between a fast remote model and a slower local one belongs to whoever asks for the item; the shortlist stays the administrator's. The chooser was removed in `a4db255` and restored by explicit user request in `54bdb18` (both 2026-09-01).

### D-074. Per-call sampling triple
- **Rule:** Every model call samples with its own temperature, top-k and top-p (`sampling.phases.<phase>.*`, resolved by `inference.sampling(phase, think)`); an empty value is inherited.
- **Date:** 2026-10-03 · **Commit:** `d3082a7` · **Status:** in force
- **Why:** Sampling was four shared temperatures and top-k/top-p were never sent, so each call took its Modelfile's values; empty keeps exactly what a call did before, so adding a phase changes no existing one.

### D-075. Queue serialises per backend lane
- **Rule:** The job queue serialises per backend lane: `local` (Ollama, capacity 1, not a setting) and `remote` (Cerebras); only generative models reserve a lane, and `backends_for` fails closed by reserving both.
- **Date:** 2026-08-27 · **Commit:** `c9fb6d0` · **Status:** in force
- **Why:** One single queue made every job wait for a machine it would never use; two local jobs would only swap weights on the one GPU.

### D-076. Remote lane holds several jobs
- **Rule:** The remote lane runs up to `CEREBRAS_MAX_CONCURRENT_JOBS` (default 4) jobs at once, which is safe only because the ledger is locked and books claims.
- **Date:** 2026-08-29 · **Commit:** `e869a24` · **Status:** in force
- **Why:** Cerebras is a rolling quota administered call by call, so two remote jobs spend the same in parallel as in series; serialising the lane only stopped two people working at once.

### D-077. Queue classes with aging
- **Rule:** Inside a lane, waiting jobs go out by class, then by arrival: A tutor and chat turns, B commissions, comparisons and `tag_item`, C everything else; B ages to A after `QUEUE_PROMOTE_B_AFTER_SECONDS` and C to B after `QUEUE_PROMOTE_C_AFTER_SECONDS`, and on the local lane background jobs hold at most `LOCAL_MAX_BACKGROUND_JOBS` slots, a cap aging does not lift.
- **Date:** 2026-10-06 · **Commit:** `5f8960a` · **Status:** in force
- **Why:** Classes follow duration and who waits (somebody waits ~30 s in a chat, somebody watches a commission's bar); aging ensures nobody waits for ever.

### D-078. Queue first come, first served
- **Rule:** Jobs run one at a time, in order of arrival.
- **Date:** 2026-08-03 · **Commit:** `77e4aa8` · **Status:** superseded by D-077
- **Why:** Ollama serves every job from a single GPU, and running two large models side by side would only swap weights; the queue makes the contention explicit.

### D-079. Interruptible generate
- **Rule:** `inference.generate()` streams internally and emits nothing; abandoning the stream closes it so the engine stops, and long waits are sliced into one-second checkpoints.
- **Date:** 2026-09-01 · **Commit:** `9bdffb2` · **Status:** in force
- **Why:** With a blocking request a stop waited for the whole answer (two cancelled transcriptions released their lane 164 s and 166 s later); streaming brought it to 0.2 s.

### D-080. Idle GPU unload after 30 minutes
- **Rule:** The API unloads every resident Ollama model after 30 minutes with no job; this does not replace `OLLAMA_KEEP_ALIVE` with a shorter timer.
- **Date:** 2026-08-18 · **Commit:** `1a949c5` · **Status:** in force
- **Why:** The keep-alive keeps a working session hot but cannot tell a pause from an abandonment, and an untouched installation kept ~29 GiB of a shared card.

### D-081. Idle clock counts every lane
- **Rule:** The idle unload clock counts jobs on every lane, remote included.
- **Date:** 2026-08-27 · **Commit:** `c9fb6d0` · **Status:** in force
- **Why:** The embedder and guardrail are local and outside the lane calculation, so a purely remote job still uses the GPU; counting only the local lane would unload the embedder under running work.

### D-082. Capped or looping page is failed
- **Rule:** A transcription answer that reaches `TRANSCRIBE_MAX_OUTPUT_TOKENS` or falls into a repetition loop (cut in the stream by `stop_on_loop`) is retried once with a note naming the loop; if still unfinished, the page is a failed page that keeps the text before the loop.
- **Date:** 2026-09-16 · **Commit:** `0a5a1b1` · **Status:** in force
- **Why:** Measured: a page of grid rows hit the 4 096-token cap three times with the same text, and another stopped on its own after 271 identical rows and was cached as content; the output cap caught only the first shape.

### D-083. Capped page fails without retry
- **Rule:** A transcription answer that hits `TRANSCRIBE_MAX_OUTPUT_TOKENS` becomes a failed page with no retry.
- **Date:** 2026-09-05 · **Commit:** `72a5ffc` · **Status:** superseded by D-082
- **Why:** Nine exam pages came back as 40 960 tokens of one repeated `\_` (~1.9 $ and ~14 min of one build); at temperature 0 the same image yields the same run, so no retry was made.

### D-084. No transcription prompt version
- **Rule:** The page fingerprint holds no prompt version; a prompt change re-reads no page, and `RETIRED_FIELDS` drops the old key on read.
- **Date:** 2026-09-16 · **Commit:** `0a5a1b1` · **Status:** in force
- **Why:** `prompt_version` expired every page of every subject whenever a prompt changed, and a prompt change is a better prompt: an older page stays current until its document changes or somebody reads it again.

### D-085. Transcription prompt version in fingerprint
- **Rule:** `TRANSCRIBE_PROMPT_VERSION` is part of the page cache fingerprint and is bumped when the transcription prompt changes.
- **Date:** 2026-08-12 · **Commit:** `9da1603` · **Status:** superseded by D-084
- **Why:** Not recorded.

### D-086. gpt-oss is not used
- **Rule:** No gpt-oss model is used, and no code names it.
- **Date:** 2026-08-28 · **Commit:** `a82b176` · **Status:** in force
- **Why:** Explicit user request (one of four in the commit); its special case for a model whose reasoning cannot be switched off (`_NO_REASONING_OFF_PREFIXES`) left with it.

## Identity and access

### D-087. Invitation-only sign-up with own auth
- **Rule:** Accounts come only from single-use invitations, the seats of a teacher's class link, or `create-user`; there is never open registration. Authentication is the system's own (own passwords and server-side sessions), with no JWT.
- **Date:** 2026-08-16 · **Commit:** `4172d33` · **Status:** in force
- **Why:** The commit dropped open registration entirely so that accounts come only from invitations or the `create-user` command, with Argon2id passwords and opaque server-side sessions.

### D-088. Username is the identity, email optional
- **Rule:** The username is the login identity; `users.email` is an optional delivery detail.
- **Date:** 2026-08-16 · **Commit:** `c64d8c4` · **Status:** in force
- **Why:** Mail is delivered by hand here, so an address was neither how anyone is named nor how anyone is found (migration 0004).

### D-089. Accounts enter a subject by link
- **Rule:** Nobody adds an account to a subject by its username: an account enters a subject with a link (a class link or a personal invitation, through `/accept` or `/join`).
- **Date:** 2026-10-07 · **Commit:** `b6b4eee` · **Status:** in force
- **Why:** Not recorded; the same commit added `/join` so that an existing account enters a subject with either kind of link.

### D-090. Account profile comes from the invitation
- **Rule:** The account's profile («Docente» / «Alumno») is the invitation's, never the registrant's answer; only the administrator raises it, nothing lowers it, and it decides one thing, creating subjects, authorising nothing inside one.
- **Date:** 2026-10-06 · **Commit:** `5fd8c5a` · **Status:** in force
- **Why:** Part of giving a subject a class (migration 0017): the profile only climbs and decides only who creates subjects; the registration form asks nothing and `/accept` ignores a profile sent to it.

### D-091. Registrant answers the evaluator profile
- **Rule:** The evaluator profile is a variable of the evaluation that the person registering chooses on the registration form; the invitation binds only the access.
- **Date:** 2026-08-27 · **Commit:** `942334c` · **Status:** superseded by D-090
- **Why:** Whoever invites had no business declaring what somebody else is, and the person redeeming the link is the one in front of a form.

### D-092. Membership checked on every route
- **Rule:** Authorisation is a membership row with viewer/editor/owner ranks, checked on every route.
- **Date:** 2026-08-16 · **Commit:** `4172d33` · **Status:** in force
- **Why:** Introduced with invite-only auth to gate every route per workspace; until then `/ws` replayed the whole bus to any connection.

### D-093. Admin bypass in one place
- **Rule:** The installation administrator's bypass of membership exists only in `auth.deps.access_for`, flagged with `Access.as_admin`.
- **Date:** 2026-08-16 · **Commit:** `c64d8c4` · **Status:** in force
- **Why:** The administrator is let through `require_member` in `access_for` and nowhere else, with `as_admin` so the UI says when the bypass is in use.

### D-094. School networks count the account only
- **Rule:** From a network the administrator lists as a school's (`access.trusted_networks`), only the account or link key is counted by the attempt limits; a bucket with no account keeps its address key.
- **Date:** 2026-10-06 · **Commit:** `7cc23f1` · **Status:** in force
- **Why:** Behind a school's NAT a class is one address, and the per-address limit refused the ninth student to log in.

### D-095. Per-address attempt limit without exception
- **Rule:** Login, invitation redemption and recovery attempts are throttled by IP and by account, with no exception for any network.
- **Date:** 2026-08-16 · **Commit:** `4172d33` · **Status:** superseded by D-094
- **Why:** Introduced with invite-only auth to throttle login, invitation redemption and recovery; no further reason recorded.

### D-096. Teachers switch what students use
- **Rule:** A subject's teachers decide whether its students generate exercises and use the tutor, with two switches of the subject (`workspaces.student_generate`, `student_tutor`) read after the administrator's mode; teachers are never bound by them.
- **Date:** 2026-10-06 · **Commit:** `e7c39fb` · **Status:** in force
- **Why:** The switches bind the subject's students alone; `features.refusal` is the one reading, the administrator's mode first, then the student's switch.

### D-097. Group switch wins over subject's
- **Rule:** A group's switch, when it says something, wins over the subject's switch for the group's students.
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** in force
- **Why:** With a group a teacher does what they do with the class, its tools included (migration 0022).

### D-098. Classes may have groups
- **Rule:** A class may have groups, and with a group its teachers do what they do with the class: its tools, its progress, its link and invitations, its activity and digest. A student is in one group at most; teachers are in none.
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** in force
- **Why:** The user's decision; the commit states that with a group a teacher does what they do with the class (migration 0022).

### D-099. One live class link per destination
- **Rule:** There is at most one live class link per destination: the class and each of its groups.
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** in force
- **Why:** A group has its own link and invitations, as the class does; who enters through them lands in the group.

### D-100. Viewer is a student
- **Rule:** The `viewer` role is «Alumno»: a student reads the syllabus without editing it and generates, evaluates or uses the tutor by their permissions (`catalogue.STUDENT_KINDS`); the rest of the construction (the bank as a teacher works it, the raw material, the types of exercise as a step) is not theirs to see. There is no fourth role.
- **Date:** 2026-10-06 · **Commit:** `a7869d2` · **Status:** in force
- **Why:** The three roles became a class (student, teacher, owning teacher); the construction's reads became `auth.EDIT` and a student queues only their own kinds.

### D-101. Viewer is a read-only «Lector»
- **Rule:** The `viewer` role is «Lector», who sees everything in the workspace and changes nothing.
- **Date:** 2026-08-16 · **Commit:** `4172d33` · **Status:** superseded by D-100
- **Why:** Introduced with the viewer/editor/owner ranks of per-workspace authorisation; no further reason recorded.

### D-102. Students read the bank as shown
- **Rule:** A student reads the bank as its teachers show it: every exercise is hidden until shown, whole or by fields, to the class or to chosen groups.
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** in force
- **Why:** Students read the bank next to the syllabus and take an exercise to a commission, the tutor or the chat (`GET /api/exercises`).

### D-103. Students do not read the bank
- **Rule:** The bank is `auth.EDIT`, reads included, so a student does not read it.
- **Date:** 2026-10-06 · **Commit:** `a7869d2` · **Status:** superseded by D-102
- **Why:** A student reads none of the construction; the bank, the raw documents and a stage's history were closed to them.

### D-104. Invitation links kept sealed
- **Rule:** Invitation links are kept sealed with Fernet under a key that is never in the database, never stored in clear; the sealed copy dies with the use.
- **Date:** 2026-09-16 · **Commit:** `8452e63` · **Status:** in force
- **Why:** A copy of the database alone opens no invitation, and a lost key leaves every link working and merely unshowable.

### D-105. Teachers bring their class in
- **Rule:** A teacher brings their class in with a class link of many uses (seats, expiry, pause, renewal) and personal invitations of their subject; an owner invites teachers. The administrator keeps every power over invitations and memberships it had.
- **Date:** 2026-10-06 · **Commit:** `b6b4eee` · **Status:** in force
- **Why:** Not recorded beyond the commit, which gives a subject one live class link and lets a teacher mint the subject's personal invitations.

### D-106. Invitations and membership are admin-only
- **Rule:** Invitations and memberships are managed by the administrator alone, from the panel.
- **Date:** 2026-08-17 · **Commit:** `5bdf914` · **Status:** superseded by D-105
- **Why:** Two screens answering one question is how two answers drift apart (the owner-scoped invite and member routes were dropped).

### D-107. Teachers pause and remove members
- **Rule:** A teacher pauses, opens and removes the students of their subjects, and the owner its teachers too. A subject with people keeps an active owner at every door; pausing is reversible and removing is not; neither moves what the person produced.
- **Date:** 2026-10-06 · **Commit:** `4fc887a` · **Status:** in force
- **Why:** `server/members.py` holds the gestures and every door goes through them; closing a membership refuses taking the last active owner from people still active (409 `last_owner`).

### D-108. No forgot-password link on login
- **Rule:** The login screen has no «forgot password» link; administrators hand out reset links.
- **Date:** 2026-09-04 · **Commit:** `db7bb84` · **Status:** in force
- **Why:** Not recorded; the door, `/reset` and `mail.py` stay, so the administrator's hand-delivered link still works.

### D-109. No password generator
- **Rule:** No screen generates passwords; the `autocomplete="new-password"` fields let the browser's own manager offer one.
- **Date:** 2026-08-27 · **Commit:** `942334c` · **Status:** in force
- **Why:** A screen that mints a password must show it in clear so it can be copied, and that box was the price.

### D-110. No session list
- **Rule:** There is no list of open sessions and no route to revoke other sessions.
- **Date:** 2026-08-17 · **Commit:** `8b0fe7a` · **Status:** in force
- **Why:** A password change already revokes every other session in the same transaction.

### D-111. Evaluators never see the score
- **Rule:** The evaluator never sees the evaluation's aggregate score; their listing shows only their own sessions.
- **Date:** 2026-08-16 · **Commit:** `c64d8c4` · **Status:** in force
- **Why:** Showing evaluators the running score of what they are about to judge invites them to even it out.

### D-112. Blind instruments before the reveal
- **Rule:** Every blind instrument (triage, forced choice, decline) is collected before the reveal; the rubric comes after it.
- **Date:** 2026-08-26 · **Commit:** `fea7d68` · **Status:** in force
- **Why:** The only scored thing was the system's variant, rated after the reveal by somebody who knew whose it was, which is neither blind nor comparable between architectures.

### D-113. Two cards with a seed-drawn rival
- **Rule:** An evaluation session shows the system's proposal and one rival (`naive` or `rag`) drawn by the session's seed; only the two drawn arms are generated.
- **Date:** 2026-09-08 · **Commit:** `be84dc1` · **Status:** in force
- **Why:** A two-way forced choice asks the question the evaluation exists to answer, whether the system beats this alternative; a third unseen proposal is a model call for a datum nobody reads.

### D-114. Admin deletion takes the files
- **Rule:** Deleting workspaces and artifacts is the administrator's and takes the files; emptying a stage removes its derived caches and never touches `.history/`.
- **Date:** 2026-08-18 · **Commit:** `d7c8bd3` · **Status:** in force
- **Why:** Not recorded beyond the commit; `destroy` refuses any path that is not a direct child of `WORKSPACES_DIR` because `rmtree` on a wrongly resolved path cannot be undone.

### D-115. Last-member deletion takes the tree
- **Rule:** A workspace deletion that leaves no other member takes its directory tree too; if others remain, the files stay. The tree goes before the row.
- **Date:** 2026-08-28 · **Commit:** `0dc9e73` · **Status:** in force
- **Why:** Abandoned instances piled up under slugs nothing recorded; if others remain the files stay because they are their notes.

### D-116. CORS off
- **Rule:** CORS is off by default; state-changing requests from another origin are rejected.
- **Date:** 2026-08-16 · **Commit:** `4172d33` · **Status:** in force
- **Why:** The commit removed the permissive CORS defaults as part of securing the API behind authentication; no further reason recorded.

### D-117. Exercises private to their author
- **Rule:** A generated exercise is private to its author: every other account gets the same 404 as a missing one.
- **Date:** 2026-09-04 · **Commit:** `db7bb84` · **Status:** in force
- **Why:** «Mine» was merely a default scope somebody could flip, so a filter was standing in for privacy; a 403 would confirm the id names something.

### D-118. Admin reads exercises from the panel
- **Rule:** The installation administrator alone reads every account's exercises, read-only, from the panel (`GET /api/admin/workspaces/{slug}/generations`), never through `/api/generations`.
- **Date:** 2026-10-03 · **Commit:** `264f0f9` · **Status:** in force
- **Why:** The «Asignaturas» tab's exercise count opens every exercise of that subject, while `/api/generations` stays private to the author, the admin included.

### D-119. Teachers read figures of exercises
- **Rule:** A subject's teachers read figures of their students' exercises (type, level, concept, day), never an exercise.
- **Date:** 2026-10-07 · **Commit:** `01319e3` · **Status:** in force
- **Why:** Approved by the user on 2026-10-07 with «Clase → Actividad»: code counts from the files without reading their text, so a teacher sees what the class does week by week.

### D-120. Teachers see no figures of use
- **Rule:** A subject's teachers see no figure of use per student; generated exercises are read by their author alone.
- **Date:** 2026-09-04 · **Commit:** `db7bb84` · **Status:** superseded by D-119
- **Why:** Exercises were made private to their author, owner and administrator included.

### D-121. Private jobs belong to their author
- **Rule:** A private job's events and job routes are its author's alone (`PRIVATE_KINDS`: commissions, comparisons, tutor turns); a build's are the subject's.
- **Date:** 2026-10-06 · **Commit:** `d411b9a` · **Status:** in force
- **Why:** The bus stamps private jobs' events with the author and every job route answers another account the same 404 as a missing job.

### D-122. Student jobs reveal nothing of the bank
- **Rule:** A student's job says nothing of the bank while it runs (the prompt text is stripped and few-shot keeps only ids, concepts and type), and a student reads no prompt or exemplar body afterwards.
- **Date:** 2026-10-06 · **Commit:** `d411b9a` · **Status:** in force
- **Why:** A student reads none of the construction; redaction is set by the route from the role, and the exercise's file keeps everything.

### D-123. Admin switches the optional functions
- **Rule:** The administrator switches the evaluation and the tutor for nobody, everybody or a list of accounts; both start off; the administrator follows the same rule as any account; an invitation may list its holder.
- **Date:** 2026-10-03 · **Commit:** `ebbe9fe` · **Status:** in force
- **Why:** One branch carries both optional functions, so each is switched from the installation; a function with no row is off, so an upgrading installation opens neither until its administrator does.

### D-124. Tutor opened for whole subjects
- **Rule:** The tutor may also be switched on for a list of subjects: everybody in a listed subject uses it there, whoever joins later included, and nowhere else.
- **Date:** 2026-10-07 · **Commit:** `7363aeb` · **Status:** in force
- **Why:** Not recorded beyond the commit (migration 0020, `feature_subjects`); the evaluation stays account by account.

### D-125. Tutor daily limit per account
- **Rule:** The tutor's daily limit (`tutor.daily_messages`) is the account's across the whole installation, counted in the database.
- **Date:** 2026-10-03 · **Commit:** `ebbe9fe` · **Status:** in force
- **Why:** Counted in the database so that deleting a conversation does not reset it; the queue is the installation's.

### D-126. Generated exercises are workspace files
- **Rule:** Generated exercises are files in the workspace, one per exercise in the author's `user_<id>/`; the database keeps none of them.
- **Date:** 2026-10-02 · **Commit:** `eba7d30` · **Status:** in force
- **Why:** The `generations` table lost most of what produced a statement; one file per exercise also means concurrent jobs never share one.

### D-127. Library returns provenance, server writes
- **Rule:** The library returns how an item was made (`GeneratedVariant.prompt`/`.provenance`) and writes nothing; the server writes the file. `uv run variatio generate` (the CLI) saves nothing.
- **Date:** 2026-10-02 · **Commit:** `eba7d30` · **Status:** in force
- **Why:** The commit moved persistence to the server: the library hands provenance over and writes nothing.

## Interface

### D-128. Atlas in clay material
- **Rule:** The client's material is Atlas in clay: no white anywhere, two levels of depth, small things flat and careful edges; the palette is measured, the arm colours are fixed and the theme is three-state.
- **Date:** 2026-10-04 · **Commit:** `e88582f` · **Status:** in force
- **Why:** The user's choice after five rounds of screenshots; the grid (black ink on white) had no identity. `check:color` fails any token lighter than L 0.93.

### D-129. The grid with ink primary
- **Rule:** The client's material is the grid (Retícula): black ink on white, `--radius: 0`, and `--primary` is the ink, not a hue, so colour appears only where it means something.
- **Date:** 2026-08-25 · **Commit:** `98274f9` · **Status:** superseded by D-128
- **Why:** With `--primary` as a near-black ink, hierarchy is carried by type, weight and width, which frees the blue family for `--arm-system` (the primary had to clear ΔE 15 against it).

### D-130. One base for every block
- **Rule:** Blocks, tables, lists, lists of sections, controls on a line, choices and tabs share one base: tables and lists of data lie flat on their block (`.well` holds only what is not a row of data, and a list that scrolls inside its block); row gestures show on hover except the one that opens; every list of sections leads with a 16 px mark; one tab, one pill, one choice card; whole-pixel lines.
- **Date:** 2026-10-07 · **Commit:** `2928970` · **Status:** in force
- **Why:** The user asked for a consistency pass after an inventory with screenshots of every screen; «Clase» and `/raw` sank their tables while «Administración» laid them flat.

### D-131. Three numbered construction steps
- **Rule:** The bar is the path: three numbered steps, «Apuntes y ejercicios», «Temario» and «Banco de ejercicios», with the types of exercise as the first part of the third.
- **Date:** 2026-10-08 · **Commit:** `5dd6f74` · **Status:** in force
- **Why:** The types were a step of their own only because deciding which concepts work as labels needs them closed; that review now heads the bank's collection.

### D-132. Four steps, types before syllabus
- **Rule:** The bar is the path of four numbered steps, the types of exercise before the syllabus.
- **Date:** 2026-08-31 · **Commit:** `c3dec33` · **Status:** superseded by D-131
- **Why:** The bar should say where a newcomer goes next; the profile led because finishing the syllabus (its taggability review) needed an approved profile.

### D-133. As many doors as open functions
- **Rule:** After the steps the bar draws one unnumbered door for each function open to the account, with no cap.
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** in force
- **Why:** The user never wanted the doors capped; the free chat added a fourth door («The cap of three doors goes»).

### D-134. Three doors at most
- **Rule:** The bar draws the unnumbered doors open to the account, up to three: «Generar ejercicios», «Evaluar el sistema» and «Tutor socrático»; no fourth door.
- **Date:** 2026-10-03 · **Commit:** `4450745` · **Status:** superseded by D-133
- **Why:** The study returned beside the tutor on one branch, giving the bar three doors after the construction.

### D-135. Steps and doors parted by a rule
- **Rule:** The bar sets the steps and the doors apart by a rule and draws no phase captions.
- **Date:** 2026-10-04 · **Commit:** `e88582f` · **Status:** in force
- **Why:** The user's request with the Atlas redraw; the guide and the tutorial still name the two phases.

### D-136. Phase captions over the bar
- **Rule:** The bar captions its two groups «Fase de construcción» and «Fase de pruebas».
- **Date:** 2026-09-03 · **Commit:** `476f6b8` · **Status:** superseded by D-135
- **Why:** Not recorded in the commit; the path had been split into two phases in `c8ef475`, so that generating sits inside the path's numbering.

### D-137. Steps never fold
- **Rule:** The construction steps in the bar never fold, done or not.
- **Date:** 2026-10-08 · **Commit:** `5dd6f74` · **Status:** in force
- **Why:** Recorded with the move to three steps (`FoldedPhase`, its `‹` and the `vg.buildSteps` preference removed); no separate reason given.

### D-138. Finished construction folds into a pill
- **Rule:** Once the four construction steps are done they fold into one pill, «Asignatura preparada · Ver los pasos», remembered per browser, with a `‹` to fold them again.
- **Date:** 2026-09-05 · **Commit:** `dffb52a` · **Status:** superseded by D-137
- **Why:** Measured at 1280 px: the strip asked 504 px folded against 883 px unfolded, in 836 px available.

### D-139. No dashboard and no rail
- **Rule:** There is no dashboard and no rail: `/` redirects to the current step, and the numbered bar is the navigation.
- **Date:** 2026-08-31 · **Commit:** `c3dec33` · **Status:** in force
- **Why:** «Panel» had nothing left to watch from outside a chain that is now the navigation, and the step numbers say what the rail encoded.

### D-140. Student bar reads syllabus and bank
- **Rule:** For a student the bar draws «Temario» and «Banco de ejercicios» without a number as the whole construction, and `/` leads to the first open door or to `SubjectNotReady`; for a teacher nothing changes.
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** in force
- **Why:** Students read the bank as their teachers show it, next to the syllabus in their bar, and take an exercise to a commission, the tutor or the chat.

### D-141. Student bar is the syllabus alone
- **Rule:** For a student the bar draws «Temario» alone, without a number, as the whole construction, then the doors open to them; `/` lands on the first open door or `SubjectNotReady`.
- **Date:** 2026-10-06 · **Commit:** `3f5bfd7` · **Status:** superseded by D-140
- **Why:** A student (`viewer`) reads the syllabus without editing it; the rest of the construction is not theirs to see.

### D-142. Step 3 shows one part at a time
- **Rule:** Step 3 is two parts, the types of exercise and then the bank, one on screen, chosen from a block of two choice cards at the top (types 3, bank 7) that says where each stands; the bank's part opens once the types exist and is where a visit opens once both are built; the part on screen is headed «Paso 3 de 3 · Parte N de 2»; «Recoger el banco» confirms the types and collects the bank; one coral control on the next move; one part corrected at a time.
- **Date:** 2026-10-08 · **Commit:** `8793250` · **Status:** in force
- **Why:** The user's request the same day; the part not on screen stays mounted and hidden, so a draft survives the switch.

### D-143. Step 3 parts stacked on one page
- **Rule:** Step 3 is one page of two parts, the types and the bank, stacked under a heading of the step and told apart by 56 px and a rule.
- **Date:** 2026-10-08 · **Commit:** `5dd6f74` · **Status:** superseded by D-142
- **Why:** The types of exercise and the bank became one step when the taggability review moved to the head of the bank's collection.

### D-144. View and correct are two moments
- **Rule:** A stage opens as a read-only view and correcting is a second moment unlocked on request; «Continuar» closes the stage, and there is no «Aprobar».
- **Date:** 2026-09-02 · **Commit:** `c8ef475` · **Status:** in force
- **Why:** «Continuar al Paso N» navigated without closing the stage, leading to a step that refused to build; «Aprobar» was a word nobody could act on.

### D-145. No «Reabrir»
- **Rule:** A closed stage is corrected through the same unlock control as any other, and the first saved change reopens it on the server; there is no «Reabrir».
- **Date:** 2026-09-02 · **Commit:** `df24b4e` · **Status:** in force
- **Why:** Every hand edit already reopened the stage on the server, so a separate reopen control added nothing.

### D-146. No rebuild except for document drift
- **Rule:** A built stage offers no rebuild, except «Volver a construir» when it was built from documents its slot no longer holds.
- **Date:** 2026-09-12 · **Commit:** `bcc1b34` · **Status:** in force
- **Why:** `df24b4e` removed the rebuild; `bcc1b34` added the drift case because a teacher who added documents after closing the steps saw every step still done.

### D-147. «Modificar» unlocks correction
- **Rule:** The control that unlocks correction is «Modificar» on every step.
- **Date:** 2026-10-15 · **Commit:** `2591988` · **Status:** in force
- **Why:** The user's request: one plain verb, on every step.

### D-148. «Quiero corregir algo» unlocks correction
- **Rule:** The control that unlocks correction is «Quiero corregir algo».
- **Date:** 2026-09-02 · **Commit:** `c8ef475` · **Status:** superseded by D-147
- **Why:** Introduced when viewing and correcting became two moments (vista → valoración → ¿quieres corregir algo? → corrección).

### D-149. Way out beside the title
- **Rule:** «Continuar» and the correction control stand to the right of the title on every step (under it below `lg`), under one line of state and with no block around them, never in a block at the foot.
- **Date:** 2026-10-05 · **Commit:** `354589c` · **Status:** in force
- **Why:** At the foot, below the whole artifact, the one control that leads anywhere was a scroll away on a long profile or bank.

### D-150. Way out in a foot block
- **Rule:** The foot of every stage carries its exits, «Continuar» and the correction control, in a closing block below the artifact.
- **Date:** 2026-09-02 · **Commit:** `c8ef475` · **Status:** superseded by D-149
- **Why:** «Aprobar» left the header and the foot of every stage got two explicit exits instead.

### D-151. Last step names its door
- **Rule:** After the last step «Continuar» is the door it opens, «Generar ejercicios».
- **Date:** 2026-10-08 · **Commit:** `5dd6f74` · **Status:** in force
- **Why:** The previous label said "first" on every visit.

### D-152. «Ya está: crear mi primer ejercicio»
- **Rule:** After the last step the closing button reads «Ya está: crear mi primer ejercicio».
- **Date:** 2026-08-31 · **Commit:** `7175ff8` · **Status:** superseded by D-151
- **Why:** Not recorded.

### D-153. Bank collection closes the bank
- **Rule:** The bank's collection closes the bank itself once it is indexed, so step 3 is done and the doors open without a press, provided the types and the syllabus are still approved.
- **Date:** 2026-10-08 · **Commit:** `87e1eb3` · **Status:** in force
- **Why:** The user's decision: a bank extracted, tagged and indexed is a finished step.

### D-154. Guide and tutorial hidden by one flag
- **Rule:** The guide and the tutorial are hidden behind `lib/help.HELP_HIDDEN`: no menu entry, no link and no route; their copy is not updated while hidden.
- **Date:** 2026-10-07 · **Commit:** `5dd6f74` · **Status:** superseded by D-225
- **Why:** The user's decision; no further reason recorded.

### D-155. A queued job is not running
- **Rule:** A queued job is never shown as running; the screen says what it waits behind and how many jobs are ahead.
- **Date:** 2026-08-27 · **Commit:** `cd488a4` · **Status:** in force
- **Why:** Launching while the engine was busy queued the job in silence, which looked like nothing happened.

### D-156. No time estimates
- **Rule:** No build or job time estimate is shown anywhere, in any form.
- **Date:** 2026-08-17 · **Commit:** `5bdf914` · **Status:** in force
- **Why:** A seconds-per-unit rate is a claim about the models; changing a model tier turned a 55-minute build into a quoted 5 h 33 m.

### D-157. No «loading model» signal
- **Rule:** No screen signals that a model is loading.
- **Date:** 2026-08-09 · **Commit:** `6580ab9` · **Status:** in force
- **Why:** Not recorded.

### D-158. No log on screen
- **Rule:** No job log is shown on screen; job lines go to `logs/<slug>/jobs.log` and no `log` event travels the bus.
- **Date:** 2026-08-31 · **Commit:** `5b41e3a` · **Status:** in force
- **Why:** The user's explicit request; the run drawer's «Registro» tab and the sink that fed it were removed.

### D-159. No run drawer
- **Rule:** There is no run drawer; a run's steps and commentary live on the stage screen and the generate screen.
- **Date:** 2026-09-01 · **Commit:** `6dccf20` · **Status:** in force
- **Why:** The «Ver ejecución» pill was its only opener; everything it held is on the stage's phase bar and the generate screen's strip.

### D-160. Generate screen belongs to the visit
- **Rule:** The generate screen shows the run launched in this visit plus any still live, and opens on the form, not on the last batch.
- **Date:** 2026-08-29 · **Commit:** `c663ec7` · **Status:** in force
- **Why:** A reload replayed the stream, greeting the user with a batch finished an hour ago, with a hard reload as the only way out.

### D-161. «Mis ejercicios» tab on generate
- **Rule:** The generate screen's «Mis ejercicios» tab lists the subject in use, and switching tabs never clears the run or its results.
- **Date:** 2026-10-04 · **Commit:** `fc3ecf8` · **Status:** in force
- **Why:** An exercise belongs to the subject it was generated in; «Generar más como este» fills the form from the tab.

### D-162. Live feed of ten rows
- **Rule:** The live feed is a window of ten rows admitting one row at a time (`features/bank/window.ts`).
- **Date:** 2026-08-29 · **Commit:** `c757cc0` · **Status:** in force
- **Why:** Updates arrive in bursts, so taking them wholesale swapped the ten rows at once and the list read as reversed and never moving.

### D-163. Zero total is not unknown total
- **Rule:** A meter with a known total of zero is finished and empty; only an unknown total sweeps.
- **Date:** 2026-08-29 · **Commit:** `8c8b145` · **Status:** in force
- **Why:** Deleting the last exemplar left the bank screen animating for ever over a workspace where nothing ran.

### D-164. KaTeX for formulas
- **Rule:** Formulas in items are typeset with KaTeX.
- **Date:** 2026-08-29 · **Commit:** `3cf3eef` · **Status:** in force
- **Why:** The generator writes TeX because the corpus does, and cards showed the source; the material needs arrows, `\text{}` and aligned arrays, which a hand-rolled subset would get wrong.

### D-165. Raw material is its own screen
- **Rule:** The raw material is its own screen (`/raw`), with one row per document.
- **Date:** 2026-08-28 · **Commit:** `5038835` · **Status:** in force
- **Why:** The documents write no artifact and feed two stages; the panel drew the same filenames twice in two components.

### D-166. What announces raw completeness
- **Rule:** Nothing announces the raw material's completeness except the finished origin's filled tick, the line over «Continuar» beside the title, and step 1's state in the bar.
- **Date:** 2026-10-05 · **Commit:** `354589c` · **Status:** in force
- **Why:** `/raw` took the same way out as the stages, beside the title; a finished origin carries a filled coral tick and no tint on its card.

### D-167. Origin tint and closing block
- **Rule:** Nothing announces the raw material's completeness except the finished origin's tinted card and the closing block at the foot of `/raw`.
- **Date:** 2026-09-02 · **Commit:** `df24b4e` · **Status:** superseded by D-166
- **Why:** `/raw` ended with the same closing block every stage had; an up-to-date origin tinted its card and carried a filled tick.

### D-168. Step 1 waits for every document read
- **Rule:** Step 1 reads done only with both origins stocked and every document read.
- **Date:** 2026-10-12 · **Commit:** `322e682` · **Status:** in force
- **Why:** The bar said «Hecho» over a screen whose one coral control was still «Procesarlos todos ahora», and `/` sent the teacher on with the reading undone.

### D-169. Step 1 done with both origins stocked
- **Rule:** Step 1 is done as soon as both origins hold a document, read or not.
- **Date:** 2026-08-31 · **Commit:** `c3dec33` · **Status:** superseded by D-168
- **Why:** That is the condition the builds behind it need; transcription is an accelerator, never a gate.

### D-170. Raw document opens beside its transcription
- **Rule:** A raw document opens in step 1 as its original beside its transcription, page to page where the transcription holds one page per page of that very file, otherwise each column scrolls on its own with one sentence saying why. It opens to read; a page is corrected from its pencil, one at a time; a page of the original keeps its white in either theme, inside a well.
- **Date:** 2026-10-08 · **Commit:** `799f2a3` · **Status:** in force
- **Why:** The tutor stopped citing places of the notes, so its document reader moved to the construction's step 1.

### D-171. Tutor's reader opens the notes
- **Rule:** A place cited under a tutor reply opens the notes in the tutor's reader as the original document, with the transcription as a second view.
- **Date:** 2026-10-04 · **Commit:** `079563b` · **Status:** superseded by D-170
- **Why:** A place under a reply opened only the transcription, one section at a time; the document itself was wanted.

### D-172. No control a teacher cannot decide
- **Rule:** A control a teacher cannot decide is not offered; the artifact fields and endpoints remain.
- **Date:** 2026-09-01 · **Commit:** `0fd8149` · **Status:** in force
- **Why:** Length bounds, «Quién lo decide», «Cómo generarlo» and «Campos que se indexan» asked for decisions with nothing on the screen to decide them with.

### D-173. No screen edits `decided_by`
- **Rule:** No screen edits `decided_by`: a build still writes it and the generate form still asks about a `decided_by: "user"` field.
- **Date:** 2026-10-05 · **Commit:** `f3fb244` · **Status:** in force
- **Why:** The user replaced «Quién lo decide» the same day with «Se elige al generar», which says what is wanted about a field.

### D-174. «Quién lo decide» back on a field
- **Rule:** «Quién lo decide» is the second row of a field in «Campos de …», with «El modelo» / «El usuario», not drawn for the statement, a list or a free object.
- **Date:** 2026-10-05 · **Commit:** `bf99d06` · **Status:** superseded by D-173
- **Why:** Explicit user request, a month after it left.

### D-175. «Se elige al generar» marks omittable fields
- **Rule:** «Se elige al generar» (`omittable`) is the second row of a field in «Campos de …» beside «Obligatoriedad», in one grid, with «Activado» / «Desactivado»; it is not drawn for the statement, and a field with it on carries a badge.
- **Date:** 2026-10-05 · **Commit:** `f3fb244` · **Status:** in force
- **Why:** Whoever prepares a subject wants to say that whoever asks for an exercise chooses whether it carries that field.

### D-176. Chosen option is ink border over ink tint
- **Rule:** The chosen option of a two-way control is the type picker's ink border over the ink tint.
- **Date:** 2026-10-05 · **Commit:** `bf99d06` · **Status:** in force
- **Why:** `--muted` and `--sunk` are one value, so a sunk pill on a muted ground was told only by the colour of its letters.

### D-177. «Campos que se indexan» stays out
- **Rule:** «Campos que se indexan» (`embed_fields`) is not offered on screen.
- **Date:** 2026-10-05 · **Commit:** `bf99d06` · **Status:** in force
- **Why:** The user removed it again on reading why the default is the statement alone (measured: a solution in the index tags worse).

### D-178. «Campos que se indexan» back on screen
- **Rule:** «Campos que se indexan» (`embed_fields`) is offered on the profile screen.
- **Date:** 2026-10-05 · **Commit:** `bf99d06` (first recorded) · **Status:** superseded by D-177
- **Why:** Not recorded; it came back for an hour and was never committed on its own.

### D-179. No (i) beside a stage title
- **Rule:** A stage's title carries no (i).
- **Date:** 2026-08-31 · **Commit:** `5b41e3a` · **Status:** in force
- **Why:** The link to the guide under the title says the same thing where the whole answer is and where it can be searched.

### D-180. An (i) never repeats visible text
- **Rule:** An (i) and visible text never say the same thing.
- **Date:** 2026-08-31 · **Commit:** `a1f1e4e` · **Status:** in force
- **Why:** The (i) per stage card repeated what the panel's heading said; six on one screen, three nearly identical, is an explanation nobody opens.

### D-181. No «Por qué este valor» in settings
- **Rule:** Settings show no «Por qué este valor»: the measured `doc` is not on screen, and an (i) appears only where a row needs one.
- **Date:** 2026-10-02 · **Commit:** `f839ca5` · **Status:** in force
- **Why:** The docs were measurements written for whoever changes a value in the code, about 1 075 characters on average and up to about 3 000, in Spanish only.

### D-182. Admin tabs are lists of sections
- **Rule:** Every tab of «Administración» is one list of its sections beside the section open, the same list on all of them; a tab with one section has none; no tiles of totals above the tabs; a list inside a block is ruled rows, never framed ones.
- **Date:** 2026-10-04 · **Commit:** `e88582f` · **Status:** in force
- **Why:** The user's request: «Motor» had a board of cells, «Configuración» a column of stages, and the functions' tabs stacked everything down one page; the lists say what the tiles said where it can be acted on.

### D-183. Own subjects and exercises only
- **Rule:** «Mis asignaturas y ejercicios» shows an account its own subjects and its own exercises only, the administrator's included; others' are read from the panel.
- **Date:** 2026-10-04 · **Commit:** `e88582f` · **Status:** in force
- **Why:** A subject reached through the admin bypass is read from the panel, not listed as the administrator's own.

### D-184. Exercises open beside the subjects
- **Rule:** In «Mis asignaturas y ejercicios» the subjects are a list and a subject's exercises open beside it, never folded under their subject.
- **Date:** 2026-10-04 · **Commit:** `d4cd682` · **Status:** in force
- **Why:** Folded under their subject, the exercises read as more subjects.

### D-185. Exercises folded under their subject
- **Rule:** Each subject of «Mis asignaturas y ejercicios» carries a fold, «Ejercicios generados», that lists its exercises under the row.
- **Date:** 2026-10-03 · **Commit:** `89df70b` · **Status:** superseded by D-184
- **Why:** The old «Mis ejercicios» tab showed a different list after every switch of subject, so subjects and exercises were joined into one screen.

### D-186. One accounts table per kind
- **Rule:** «Cuentas» is one table per kind of account, with the same columns on each, and a row carries no figure of what the account produced.
- **Date:** 2026-10-04 · **Commit:** `d4cd682` · **Status:** in force
- **Why:** What an account evaluated is read in «Evaluaciones», so the counts of exercises and comparisons and «ver sus sesiones» left the row.

### D-187. Each account kind is a section
- **Rule:** Each kind of account is a section of the tab's list, opening its table alone, with one search over the list across all kinds.
- **Date:** 2026-10-04 · **Commit:** `01061cb` · **Status:** in force
- **Why:** Stacked down one page, the students sat under every teacher and the deactivated under everybody.

### D-188. Account tables stacked on one page
- **Rule:** The tables of each kind of account are stacked down one page of «Cuentas».
- **Date:** 2026-10-04 · **Commit:** `d4cd682` · **Status:** superseded by D-187
- **Why:** «Cuentas» had been one table of every account; it was split into one table per kind.

### D-189. Configuration is one screen per stage
- **Rule:** «Configuración» is one screen per stage, named as the bar names them; a shared setting is one value, drawn on every stage that reads it and unfolded only on its owner's.
- **Date:** 2026-10-03 · **Commit:** `8f15aff` · **Status:** in force
- **Why:** Seven sections by kind of setting meant visiting most of them to tune one stage; a shared value unfolded on its owner's screen means the fold never hides the only copy.

### D-190. Optional function's stage in its tab
- **Rule:** An optional function's stage lives in that function's own admin tab, under who may use it, not in «Configuración».
- **Date:** 2026-10-04 · **Commit:** `fc3ecf8` · **Status:** in force
- **Why:** The «Evaluaciones» and «Tutor» tabs each hold who sees the function and its configuration, which leaves «Configuración».

### D-191. The mark is three equal squares
- **Rule:** The mark is three equal squares: settled, attention and outline.
- **Date:** 2026-08-31 · **Commit:** `5b41e3a` · **Status:** in force
- **Why:** The user's explicit request; the connectors went, and the stroked outline square overhung the band, so it was inset to paint the same box as the solid ones.

### D-192. Every URL path is English
- **Rule:** Every URL path is English.
- **Date:** 2026-08-28 · **Commit:** `f74b52a` · **Status:** in force
- **Why:** Not recorded beyond the rename; the invitation and reset links are minted server-side, so the rename covered the server too.

### D-193. A refusal names its way out
- **Rule:** A refusal names the move out of it (`ChainGate` names the pending stages and links to the first).
- **Date:** 2026-09-01 · **Commit:** `a4db255` · **Status:** in force
- **Why:** «Comparación bloqueada · Sin aprobar: Tus ejercicios» named a state and no move, and was reported as a broken screen.

### D-194. Profile edited through the form alone
- **Rule:** The exemplars profile is edited through the form alone.
- **Date:** 2026-08-31 · **Commit:** `5b41e3a` · **Status:** in force
- **Why:** The user's explicit request; with the raw-JSON view gone there was nothing left to switch to, so the tab strip went too.

## Tutor

### D-195. One door per function open
- **Rule:** After the construction the bar draws as many doors as functions are open to the account: «Generar ejercicios», «Evaluar el sistema», «Tutor socrático» and «Chat libre».
- **Date:** 2026-10-14 · **Commit:** `2591988` · **Status:** in force
- **Why:** The user never wanted the doors capped; the free chat arrived as a fourth function and «the cap of three doors goes».

### D-196. Three doors at most
- **Rule:** After the construction the bar has three doors, «Generar ejercicios», «Evaluar el sistema» and «Tutor socrático»; there is no fourth door.
- **Date:** 2026-10-03 · **Commit:** `4450745` · **Status:** superseded by D-195
- **Why:** The study returned beside the tutor and one branch carried both, ending the two-door rule of the tutor's branch.

### D-197. Tutor replies queue and arrive whole
- **Rule:** The tutor's replies wait in the queue like any job and say «en cola»; they are shown whole, after the checks, never streamed.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** in force
- **Why:** Code checks every reply before it is shown (a failure is retried once, then a fixed question is sent), and the local engine queues a turn, so the screen says so.

### D-198. Conversations private to their author
- **Rule:** A tutor conversation is private to its author; the installation administrator reads it read-only.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** in force
- **Why:** Conversations are files under the author's `user_<id>/`, private to the author and read-only to the admin from «Asignaturas»; a turn's job carries no text because a job is read where its conversation is not.

### D-199. Teachers read figures and a paraphrased digest
- **Rule:** A subject's teachers read, of the class and of each student, figures and a weekly digest written in paraphrase, which the teacher asks for — never a student's sentence, never a name, never a conversation; the students are not told.
- **Date:** 2026-10-07 · **Commit:** `01319e3` · **Status:** in force
- **Why:** The user's decision of 2026-10-07: teachers see what the class does week by week; a theme that copies more than 8 running words or names a student is asked again once, then dropped.

### D-200. Teachers read nothing of conversations
- **Rule:** A subject's teachers read nothing of their students' tutor conversations, not even figures.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** superseded by D-199
- **Why:** Conversations were private to their author and read only by the installation administrator; commit 01319e3 records that it changed this closed decision.

### D-201. Criteria generated, curated by teachers
- **Rule:** The subject's criteria are generated by the system and curated by a teacher with the edit role; a student never sees or changes them.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** in force
- **Why:** The criteria are an artifact of their own: a draft the system writes per unit, every criterion citing its evidence, and a curated copy that wins; only a member with edit rights builds or edits them.

### D-202. Method rules fixed and prompt-only
- **Rule:** The method's rules (`METHOD_RULES`) are fixed, not editable, and live in the prompt alone; no route returns them and no screen lists them.
- **Date:** 2026-10-03 · **Commit:** `641544f` · **Status:** in force
- **Why:** Fixed method rules sit above the criteria and nobody edits them (11abc29); 641544f moved them into the prompt alone. No further reason recorded.

### D-203. Earlier concepts are taken as known
- **Rule:** What the syllabus places before the concept asked about is taken as known: the reply neither quizzes the student on it nor steers towards it, and the focus never moves back into the prerequisite closure of the current focus.
- **Date:** 2026-10-03 · **Commit:** `641544f` · **Status:** in force
- **Why:** A question about recursion had been walked back through functions and procedures.

### D-204. Student may choose one concept
- **Rule:** The student may say what a message is about by choosing ONE concept beside the box; choosing is optional, units organise the choice and are never themselves chosen.
- **Date:** 2026-10-03 · **Commit:** `8690cc0` · **Status:** in force
- **Why:** A chosen concept, validated against the graph, leads the focus without anything being deduced. Not otherwise recorded.

### D-205. Concept maps drawn by code, sparingly
- **Rule:** Diagrams of the graph are drawn by code from the graph and shown only on a concept's first reply and on a send-back to a prerequisite; the model draws none, and a reply with its own diagram fails a check.
- **Date:** 2026-10-03 · **Commit:** `8690cc0` · **Status:** in force
- **Why:** The map is one hop of the graph around the focus, sent as data; a reply that draws a diagram of its own fails the `diagram` check.

### D-206. Formulas are the model's
- **Rule:** A reply may write formulas between dollar signs (drawn by KaTeX), only where clearer than the sentence it replaces; no code check counts or caps them.
- **Date:** 2026-10-03 · **Commit:** `8690cc0` · **Status:** in force
- **Why:** Not recorded.

### D-207. Replies speak in their own words
- **Rule:** A reply tells the material in its own words and sends the student nowhere: no «en los apuntes», no unit, section or document, no places under it, and no document reader in the tutor; the document reader belongs to step 1 of the construction.
- **Date:** 2026-10-08 · **Commit:** `799f2a3` · **Status:** in force
- **Why:** The user's decision of 2026-10-08; measured on a script of 20 messages in two subjects, 18 replies named «apuntes» before and none after.

### D-208. Places under a reply open the original
- **Rule:** The places listed under a reply open the cited document as its original (PDF pages, slides, Word file), with the transcription as a second view «Texto».
- **Date:** 2026-10-04 · **Commit:** `079563b` · **Status:** superseded by D-207
- **Why:** A place had opened the transcription one section at a time; the original document reads as its author laid it out.

### D-209. Places under a reply open the notes
- **Rule:** Code lists the card's places under each reply, and each opens the notes reader on the cited section of the transcription.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** superseded by D-208
- **Why:** Not recorded.

### D-210. One typeface in the tutor
- **Rule:** The tutor uses the system's one typeface, Archivo; the two voices differ by material and side, not by letter.
- **Date:** 2026-10-03 · **Commit:** `8690cc0` · **Status:** in force
- **Why:** The tutor read in Literata for one afternoon and the user took it back: one face across the system.

### D-211. Concept map as chips with traced lines
- **Rule:** The concept map is a graph of the app's chips with traced SVG lines, not a Mermaid diagram, and has no source to show; every relation it holds is drawn, none is written under it as a sentence, and the concept carries no unit.
- **Date:** 2026-10-08 · **Commit:** `799f2a3` · **Status:** in force
- **Why:** The user's request for a better look that keeps the graph's shape; the user corrected the same day that every relation be drawn and no unit shown.

### D-212. Concept map as a Mermaid flowchart
- **Rule:** The client writes the concept map as a Mermaid flowchart in the palette's tokens, which cannot be turned into its source.
- **Date:** 2026-10-03 · **Commit:** `8690cc0` · **Status:** superseded by D-211
- **Why:** The map is drawn by code from the graph, never by the model, and sent as data for the client to write. No reason recorded for Mermaid itself.

### D-213. Tutor screens with the guardrail alone
- **Rule:** The tutor screens a message with the guardrail alone (`screen_message`), not with admissibility.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** in force
- **Why:** Admissibility rules on commissions, not on a student's message.

### D-214. Bank solutions never enter the card
- **Rule:** When a message is a bank exercise, the card carries that exercise and an easier one, but never its solution.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** in force
- **Why:** Not recorded.

### D-215. No dedicated classifier model
- **Rule:** No "System One" classifier (Jev, Laya…) decides a message's kind; signals decide first (bank match, an exercise the conversation opened on), then one grammar call.
- **Date:** 2026-10-03 · **Commit:** `11abc29` · **Status:** in force
- **Why:** Not recorded.

## Documentation and layout (the refactor plan, 2026-10-16)

### D-216. The library's door and its Workspace
- **Rule:** `entrypoints/` is the library's public door. `builders/` and `loaders/` take a `Workspace` only to resolve their own paths; `runtime/`, `prompts/`, `wording/` and `settings/` do not import it.
- **Date:** 2026-10-16 · **Commit:** `18e03df` · **Status:** in force
- **Why:** The earlier rule was never true: six modules of `builders/` and `loaders/` took a `Workspace` from before the rule was written, and no test checked it. The new rule says what the code does; an import contract will check it (plan phase F5).

### D-217. Only entrypoints take a Workspace
- **Rule:** Only `entrypoints/` takes a `Workspace`.
- **Date:** 2026-09-08 · **Commit:** `94af439` · **Status:** superseded by D-216
- **Why:** One door into the library, and components that do not know what a subject is.

### D-218. Who imports the engine boundary
- **Rule:** Inside `variatio/`, only `cli.py`, `builders/`, `runtime/` and `core/` import `core.inference`; `core/repair.py` calls it on behalf of `builders/` and `runtime/`.
- **Date:** 2026-10-16 · **Commit:** `18e03df` · **Status:** superseded by D-230
- **Why:** The earlier rule was false (`core/repair.py` calls `inference.generate`) and no test checked it. The new rule is what the code does; an import contract will check it (plan phase F5).

### D-219. Only builders and runtime call the model
- **Rule:** Only `builders/` and `runtime/` call the model.
- **Date:** 2026-09-08 · **Commit:** `94af439` · **Status:** superseded by D-218
- **Why:** The engine is reached from the packages of work alone; the vocabulary never calls it.

### D-220. One register of decisions
- **Rule:** Every closed decision is an entry of `DECISIONS.md`, with a number, date, commit, reason and status; `AGENTS.md` keeps the one-line rule and its number.
- **Date:** 2026-10-16 · **Commit:** `5604d5c` · **Status:** in force
- **Why:** In `AGENTS.md` a decision had no number, its commit was not named and its history sat in parentheses; the Explore and Plan agents, which do not load `AGENTS.md`, could not see the decisions at all.

### D-221. Closed decisions as a section of AGENTS.md
- **Rule:** The closed decisions are a section of `AGENTS.md`, each a rule whose reason is in the commit that introduced it.
- **Date:** 2026-10-01 · **Commit:** `98bf7d4` · **Status:** superseded by D-220
- **Why:** The agent sees the rules it must not undo in the file it loads every session.

### D-222. Private plans in /plans/
- **Rule:** Work plans are written in `plans/`, which git ignores. There is no `docs/` folder: a versioned document lives at the root or beside its code.
- **Date:** 2026-10-16 · **Commit:** `18e03df` · **Status:** in force
- **Why:** `docs/` only ever held plans; with plans elsewhere it served nothing. The old pattern `docs/` also ignored any folder of that name at any depth.

### D-223. A narrative per folder
- **Rule:** The why of a folder lives in that folder's `AGENTS.md`, and the why of a decision in `DECISIONS.md`. The root `AGENTS.md` holds at most 200 lines.
- **Date:** 2026-10-16 · **Commit:** `96f850e` · **Status:** in force
- **Why:** `AGENTS.md` grew from 55.6 KB to 192 KB in 14 days (about 48 000 tokens every session); Claude Code's guidance asks for under 200 lines per file.

### D-224. Narrative belongs in AGENTS.md
- **Rule:** Comments are rare; narrative belongs in `AGENTS.md`.
- **Date:** 2026-10-01 · **Commit:** `98bf7d4` · **Status:** superseded by D-223
- **Why:** One place for the why, which the agent reads every session.

### D-225. The guide and the tutorial are deleted
- **Rule:** The hidden guide and tutorial, their routes, their catalogue keys and `lib/help` are deleted; their text stays in git history.
- **Date:** 2026-10-16 · **Commit:** `184b5de` · **Status:** in force
- **Why:** 8 009 lines (10 % of `web/src`) and 80 keys per language describing four steps when the application has three, kept behind a flag nobody turns on.

### D-226. Import boundaries checked by import-linter
- **Rule:** Python import boundaries are contracts of import-linter (a dev dependency); the client's are checked by `pnpm check:layers`.
- **Date:** 2026-10-16 · **Commit:** `b03029f` · **Status:** in force
- **Why:** Only `consumers/` had a boundary test, a hand-written `ast` walk; nothing checked the library's layers or the client's direction.

### D-227. The server by areas
- **Rule:** `server/` is organised by areas — `core/`, `auth/`, `workspaces/`, `pipeline/`, `raw/`, `kg/`, `bank/`, `classroom/`, `admin/` (one module per panel tab) — each with its routes, services, `AGENTS.md` and tests in `tests/server/<area>/`; no route is imported by another module.
- **Date:** 2026-10-16 · **Commit:** `f8d7050` · **Status:** in force
- **Why:** One area of the product was spread over up to ten files in four folders, and routes were used as libraries. Without those routes, the job handlers and `singletons.py`, the areas' services form no cycle.

### D-228. Document code outside the builders
- **Rule:** The document plumbing (`builders/source_docs/`) lives in `variatio/documents/`.
- **Date:** 2026-10-16 · **Commit:** `ed3abf7` · **Status:** in force
- **Why:** Three server modules, two functions and `entrypoints/transcribe.py` import it, and the transcription is no builder.

### D-229. Client types, hooks and primitives split
- **Rule:** `lib/types.ts` and `state/queries.ts` are split by area behind an `index.ts`; `components/ui/misc.tsx` becomes one primitive per file.
- **Date:** 2026-10-16 · **Commit:** — · **Status:** decided; applies in plan phases F22 and F23
- **Why:** 1 476 and 1 269 lines with 139 and 55 importers; `misc.tsx` held ten primitives under a name that says nothing, and shadcn creates one file per primitive.

### D-230. Who imports the engine boundary, with documents/
- **Rule:** Inside `variatio/`, only `cli.py`, `builders/`, `runtime/`, `documents/` and `core/` import `core.inference`; `documents/pages/` transcribes with the vision model, and `core/repair.py` and `core/vectors.py` call it on behalf of `builders/` and `runtime/`.
- **Date:** 2026-10-16 · **Commit:** `ed3abf7` · **Status:** in force
- **Why:** D-228 moved the document code, page transcription included, out of `builders/`: the rule names the package the transcription now lives in, and the contracts still keep `entrypoints/`, `loaders/`, `prompts/`, `wording/` and `settings/` away from the engine.
