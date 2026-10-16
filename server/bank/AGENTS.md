# AGENTS.md — `server/bank/` — step 3, «Banco de ejercicios»

Read the root `AGENTS.md` and `server/AGENTS.md` first. The closed decisions are numbered in
the root `DECISIONS.md`. The screen is `web/src/features/bank/AGENTS.md`; the chain that
collects and closes the bank is `pipeline/AGENTS.md`.

`routes/` holds `/api/bank` (the teacher's bank, `auth.EDIT`, reads included), `/api/exercises`
(the class's reading, `auth.VIEW`) and `/api/profile` (the types of exercise). `edit.py` edits
the bank, `reading.py` cuts it to what a reader may see, `marks.py` keeps who sees each
exercise and a teacher's stars, `tagging.py` queues the tagger on the exercises picked, and
`profile_edit.py` edits the types.

- **A student reads the bank as its teachers show it** (D-102): every exercise is hidden until
  shown, whole or by fields, to the class or to chosen groups, through `reading.py` alone.
  The tutor and the chat open a conversation on an exercise of the bank only through
  `reading.readable`.
- **An exercise of a closed bank, corrected, seals the bank again** (`edit._persist`, the
  user's decision of 2026-10-14) when it was closed behind closed types and syllabus and
  stale for nothing; a draft stays a draft.
- **The marks are not content**: no hash, no approval moved. They name an exercise by its
  content (`marks.keys`), never by its id, so a re-extraction keeps them and editing a
  statement carries them (`routes/bank.patch`).

## The bank's build

- The bank checkpoints per document into `artifacts/.exemplars_bank.building.json` and writes
  `exemplars_bank.json` once at the end, starting empty (`C001`); cancelling loses the run;
  the parent sweeps the working file. **What a person added survives a re-extraction**
  (2026-10-14): the handler hands the build the bank's `manual` and `generated` exercises as
  a seed (`bank_edit.seed`, `artifacts/.exemplars_bank.seed.json`, `build_worker --keep`),
  the builder starts from them with their ids and tags and drops an extracted exercise that
  repeats one (`ExemplarsBankBuilder.build(keep=)`). One that no longer fits its type is put
  aside once the new bank is in place (`artifacts/.bank_set_aside.json`), and the bank's page
  offers it back, corrected through «Nuevo ejercicio» as it was (`POST /api/bank`
  `set_aside`), or lets it go. The confirmation of «Extraer el banco otra vez» says what is
  kept and how many collected exercises carry marks that only an identical statement keeps.
