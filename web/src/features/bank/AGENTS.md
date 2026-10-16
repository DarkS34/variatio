# AGENTS.md — `web/src/features/bank/` — step 3, «Banco de ejercicios»

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Read `web/AGENTS.md` and `web/DESIGN.md` first. The server's side is `server/routers/bank.py`,
`server/editors/bank_edit.py` and `server/bank_marks.py`.

## The screens of step 3

- **Step 3, «Banco de ejercicios»** (`/prepare/bank`, `features/bank/BankStep.tsx`; the
  user's decision of 2026-10-08, which merged the steps «Tipos de ejercicio» and «Banco de
  ejercicios»; `/prepare/profile` redirects here): TWO parts, ONE on screen — the types of
  exercise (`ProfilePart`, the profile editor under a headless `StageGate`), then the bank
  (`BankPart`). A block at the top, under the bar, chooses the part (`PartPicker`, the user's
  request of the same day, drawn as the engine's choice): two `CARD_CHOICE` cards, the types
  three tenths of the line and the bank seven from `xl` (halves below it, stacked on a
  phone), each with the square of the choice, its name, its state as a `Badge` in the bar's
  words and tones («Hecho», «Te toca ahora» in coral, «Después», «Construyendo», plus
  «Modificando» and «Con cambios») and one sentence of what it is. They are tabs
  (`role="tab"`, the keys of `useRadioGroup`); the panel not on screen stays mounted and
  hidden, so a draft survives the switch. Where each part stands, which may be opened and
  which a visit opens on is `features/bank/parts.readParts`, tested: the bank's card is
  disabled — «Después» with a lock, the reason in place of its sentence — until the types
  exist, and once they are built it says «Te toca ahora» (at most one part does), and «Hecho»
  once the bank is extracted and tagged, closed or not; a visit
  opens on the bank once both parts are built (the user's request), or while its collection
  runs or where it stopped, else on the types. Under the block the part on screen is headed
  as a step is: «Fase de construcción · Paso 3 de 3 · Parte N de 2», its name as the title,
  what it is, and its way out (`WayOn`) — «Modificar» and the coral: on the types
  «Continuar a la Parte 2», which saves their draft and shows the bank without closing them
  (the types are confirmed when the bank is collected or closed, so a bank collected with
  other types is still offered again); on the bank «Generar ejercicios», which closes both
  (the collection has closed the bank already, so it is the door),
  or «Extraer el banco otra vez» (types changed since, or the bank stale; asked first, the
  bank's corrections go) beside an outline «Seguir con este banco» where the bank can be
  closed as it is, or «Ir al Paso 2 · Temario» while the syllabus is open. With no bank the
  bank's part is the call in the middle, as every unbuilt stage: «Recoger el banco» — which
  saves the types' draft, closes them and queues the review that heads the collection. ONE
  coral control on the screen. Only one part is corrected at a time (one sticky bar). The
  bank's part draws no «Bloqueado» for types still open, since its own moves close them;
  only an open syllabus blocks it, in the step's words.
  While a collection runs the bank's part shows its three links as ruled rows (each job named
  as every screen names it: «Decidir qué conceptos sirven de etiqueta», «Recoger los ejercicios
  y etiquetarlos», «Preparar el banco para generar»; a skipped review says «Sin cambios desde
  la última vez») and under them the running link's progress card; a stopped collection
  keeps the rows with the failure and offers «Recoger el banco» under them.
- Bank (the second part of step 3): seven rows a page, every collapsed row the same height,
  bounded cells, `table-fixed`, filters (search, modality, source, level, «Sin concepto»),
  no ordering control, no similarity scores, primary concept as a filled badge placed first.
  `ConceptBadge`/`ConceptChip` are the two ways to draw a concept; badges truncate with a
  `title`. Where an exercise comes from (2026-10-14, the user's request): «Manual» or
  «Generado» beside its id, with who added it and when in the `title`; collected from the
  documents is the ordinary case and says nothing. The source filter opens with «Manuales»
  and «Generados» over the documents. **A teacher writes exercises** with «Añadir
  ejercicio» at the end of the filters, in either moment of the stage
  (`features/bank/AddExercise.tsx`, `POST /api/bank`): a dialog of two numbered steps —
  «El ejercicio» (type, level with its rung's clause, the fields in the profile's order,
  the statement first, each helped by the profile's description, «Vista previa» drawn as
  the exercise is read) and «Sus conceptos» (two choice cards: «Que lo etiquete el sistema»,
  chosen at the start, or «Los elijo yo» with the concept picker) —; saving does not close it:
  it shows the exercise and its concepts as they arrive (queued, being tagged, chosen;
  «Elegirlos yo» when the tagger found none), with «Añadir otro», which keeps the type and
  the level, and «Cerrar», after which the table opens on «Manuales» at its last page. The
  system tags it with `tag_item` (queued by the route, the gates of `tag` checked before
  anything is written; class B, its author's), whose concepts are merged into the bank as it
  is when they arrive (`bank_edit.apply_tags`): the teacher goes on adding meanwhile. A row
  the tagger is on says «Etiquetando». Editing the statement of a tagged exercise offers
  «Guardar y volver a etiquetar» (`POST /api/bank/tag`). All of it is drawn only when the
  listing says `origins`, which the demo's does not. **Two tabs over the table** (the same
  day): «Banco», what the generator learns from, and «Generados», the exercises THIS teacher
  generated in the subject (`features/bank/GeneratedList.tsx`, `GET /api/generations` with
  `bank=in|out` and `difficulty`), opening on «Fuera del banco» beside «En el banco» and
  «Todos»; two tabs and not three by origin, because an exercise passed in is both. Each row
  keeps its one gesture in sight: «Pasar al banco» (`features/bank/Promote.tsx`, the same
  dialog opened on the exercise as read, with «Corregir antes de pasarlo»; a field the
  commission left out opens it to write it, since an exemplar carries every field of its
  type; the correction goes to the bank and never to the generated file), or «En el banco ·
  G012», which shows that row in «Banco». The rows say `in_bank` (the bank's id while it is
  still there) and `promotable` (a teacher's own, out of the bank); a student is told
  neither. «Pasar al banco» is offered the same way on a teacher's saved results of
  «Generar ejercicios» and on «Mis ejercicios» of the subject in use. **Marks** (the same
  day; `server/bank_marks.py`): what the class sees of each exercise — nothing (every
  exercise starts hidden), all of it, or the fields chosen among the type's own but the
  difficulty, the statement always — and one teacher's stars. Neither is content of the
  bank: no hash, no approval moved. Both name an exercise by its CONTENT (`bank_marks.keys`:
  type and folded statement, `~2`, `~3` for the repeats of one statement in the bank's
  order), never by its id, so a re-extraction keeps them and editing a statement carries
  them (`routers/bank.patch`). Who sees what is the subject's
  (`artifacts/.bank_visibility.json`, exported with the instance); a star is a row
  (`bank_favourites`, migration 0021). On screen: «Visible» or «Visible: N campos» beside
  the id, an eye on hover that opens «Lo que ve la clase de …» (`features/bank/Visibility.tsx`:
  «Nada» / «Todo el ejercicio» / «Algunos campos» and the fields), the same for the rows
  ticked («Qué ve la clase (n)» at the table's foot; rows may be ticked in either moment of
  the stage, since this is no correction), a star that stays filled with an ink edge down
  its row, and «Todos» / «Visibles para la clase» / «Mis favoritos» before the filters.
  «Nuevo ejercicio» and «Pasar al banco» ask «¿Qué ve la clase?» too. **Who sees it**
  (2026-10-14, after the groups): where the class has groups, the same dialog asks «¿Quién
  lo ve?» — «Toda la clase» or «Algunos grupos» and the groups ticked, saving none refused
  (422, and the button waits) — the entry keeping `groups` (`bank_marks.seen_by`), the badge
  naming them («Visible · Grupo A»). Deleting a group takes it out of every entry and hides
  again what it alone saw (`bank_marks.forget_group`, from the route: SQLite gives a deleted
  id again).
- **A student's «Banco de ejercicios»** (`features/bank/BankReader.tsx`, the user's decision
  of 2026-10-14): the page a teacher works on with nothing that writes — its header with no
  number, two tabs, «Banco» (`GET /api/exercises`, opened when it holds something) and «Mis
  ejercicios generados» (`GeneratedList reading`: theirs, with no question about the bank),
  under `ReadingScope`. The table is the bank's — statement clamped, concepts, level — with
  the filters a reader asks (search, type, level, and the concepts the exercises read carry,
  under their units, `concepts` in the answer), no origin, star, eye or tick. A row unfolds
  into what was shown (`ItemFields`) and keeps its two gestures in sight, each where its
  function is open to the student: «Generar más como este» (`exercise.commissionLike`: its
  type, level and concepts, the primary first) and «Trabajar con el tutor», which carries
  the statement and the exercise's id (`bank_id`) and nothing hidden.
