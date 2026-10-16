# AGENTS.md — `web/` — the client

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Before building or changing any UI, read `web/DESIGN.md`. Screens with rules of their own have
an `AGENTS.md` in their folder: `src/features/bank/`, `src/features/class/`,
`src/features/admin/`, `src/features/raw/`, `src/consumers/tutor/`, `src/landing/`.

## The web interface (`web/`)

**Before building or changing any UI, read [`web/DESIGN.md`](web/DESIGN.md)**: the rulebook
for every block, table, list, control, choice, tab, caption and colour, with the primitive to
use for each and a checklist to run on every element. It is the prescriptive half of what
this section explains; when the two disagree, fix both in the same change.

## Navigation and the three steps

- [lib/steps.ts](web/src/lib/steps.ts) is the single home of the path: `STEPS` (raw
  material, graph, bank, numbered 1-3: the «Fase de construcción»; until 2026-10-08 four, the
  types of exercise a step of their own before the syllabus) and `USES` (the unnumbered doors
  of «Fase de pruebas»: «Generar ejercicios», «Evaluar el sistema», «Tutor socrático» and,
  since 2026-10-15, «Chat libre», which has no tone and opens with the session's
  `features.chat`). Each door names its `feature`; the bar draws
  `usesFor(useFeatures())`, so a function closed to the account has no door, and its route
  draws «not found». The bar no longer captions the two phases (user's request, 2026-10-04):
  a rule sets the groups apart. The first not-done step is `now`; done steps show a bare tick, no box. **Step 1 is done with
  both origins stocked AND every document read** (`raw/progress.rawStepDone`, through
  `useTranscriptionSummary.stepDone`, read by the bar and by `/`'s redirect; the user's
  decision of 2026-10-12 — until then documents in both origins were enough, and the bar
  said «Hecho» over a screen whose one coral control was «Procesarlos todos ahora»). Until
  the readings land the stocked origins answer, so a subject read long ago never flashes. A step names every
  artifact it closes (`artifacts`): step 3 is done with the types of exercise AND the bank
  closed, and spins while either builds or the review that opens a collection runs. Doors are
  half-dimmed and unclickable until construction is complete. **The steps never fold**
  (2026-10-08; with four they folded into one pill «Asignatura preparada» once done, with a
  `‹` to fold them again). From `xl` the bar sits on the header's centre line while it fits
  there; when it does not, it takes the line under the header, measured, never a fixed
  breakpoint. The current pill is scrolled
  into sight. There is **no dashboard**: with a session `/` redirects to the current step
  (without one it is the landing, `web/src/landing/AGENTS.md`). An account in no
  subject sees `NoWorkspace`: a teacher, the form that starts one; a student, the sentence
  that sends them to their teacher's link. Creating — there and in the switcher — is offered
  to a teacher only (`useCanCreate`, the session's profile).
- **A student's path** (role `viewer`, `useIsStudent`; decided 2026-10-06): the bar draws
  `STUDENT_READS` — «Temario» and, since 2026-10-14, «Banco de ejercicios», each with an icon
  where a step has its number — as the whole construction, then the rule and the doors open
  to them; all of it half off until the construction is closed, the reason «Tu docente
  todavía está preparando esta asignatura». `STUDENT_HIDDEN` (`/raw`, and `/prepare/profile`,
  whose redirect would land them on the bank) draw «not found»; `/prepare/bank` draws
  `BankReader` for them (`web/src/features/bank/AGENTS.md`); every other
  route of the subject draws `SubjectNotReady` (no button) until `generation_unlocked`; `/`
  lands a student on `studentLandingPath` — generating, then the tutor, the chat, then the
  evaluation, else the syllabus. `useRaw` and `useCoverage` are never asked for a student.
- A step with a running job spins a wheel (`stepBusy`); queued is never busy.
- Vocabulary seen by teachers: «Apuntes y ejercicios», «Temario» (the step, with no article;
  «concepto» for a node; «grafo» only for the structure), «Banco de ejercicios» (the step)
  with its two parts «Tipos de ejercicio» and «Banco de ejercicios», «Recoger el banco» (what
  starts its collection), «leer», «sirve de etiqueta», «asignatura» for a workspace,
  «ejercicio(s) generado(s)» for output. Steps 3 and 4 were «El temario» and «Etiquetado»
  until 2026-10-05 (user's request). A sentence that takes a step's name quotes it («…»)
  and never lowercases it: the names carry no article to lean on.
  Identifiers, routes and keys keep their names. The app never narrates itself in the first
  person; the reader's own answers may be first person.
- Every URL path is English.
- `/` is the landing for a visitor without a session and the application's redirect for an
  account; the login form is `/login` and the demo `/demo`, both public (`web/src/landing/AGENTS.md`).

## Stage screens (`StageGate`)

- An unbuilt stage shows its header and one central `xl` «Comenzar construcción» block
  (`BuildButton` decides every reason not to offer it; there is no rebuild except a
  document-stale stage). A stage opens in a read-only **review** state; «Modificar» (until
  2026-10-15 «Quiero corregir algo»; the user's request: one plain verb, on every step)
  unlocks correction, with a sticky bottom bar carrying the save state and «Guardar los
  cambios»; «Continuar» (big, `--attention`) saves-and-approves and moves on. **Both stand
  to the right of the title** (under it below `lg`), under one line of state and with no
  block around them (`StageGate.WayOn`, the steps' one way out; user's request,
  2026-10-05: at the foot they sat below the whole artifact); the group hangs from
  the TOP of that line, so «Continuar» is at one height on every step whatever the
  length of the explanation (centred, it moved with it), takes half the line at most, and
  wraps in reverse so «Continuar» keeps the first line; the sentence the foot block carried
  is the `title` of the button it explains. After the last step «Continuar» is the door it
  opens, «Generar ejercicios» (`continueLabel`; until 2026-10-08 «Ya está: crear mi primer
  ejercicio», which said "first" on every visit).
  No «Aprobar» or «Reabrir». No tags or (i) beside a stage's title. The header is `StageHeader` (kicker «Paso N de 3», `STEPS.length`; for a step
  drawn in parts, `part` joins the part's place to it, «Paso 3 de 3 · Parte 1 de 2»), and a
  stage's state for the visit — correcting, the pending edit, whether it wrote, closing it —
  is `useStageControl`, which `StageGate` makes for itself or is handed (`control`); with
  `headless` it draws its body alone. That is how the bank's step draws two stages, each
  under the header of its own part (`web/src/features/bank/AGENTS.md`).
- The stage questionnaire unfolds under its button at the foot of the artifact, on every
  built stage, for an account the evaluation is open to AND whose role may correct the
  subject (`useAsksStageReview`: editor or owner, because its routes that record are
  `auth.EDIT`; a viewer could fill it in and never save it). All of it is
  `consumers/evaluation/StageReviewSlot`, which `StageGate` loads lazily; the stage reports only whether
  this visit wrote. Its save button is ink, never `--attention`: «Continuar» is on screen.
- A rebuild hides the old artifact without deleting it. A queued job draws no progress bar.
  «Pasos» of a build start folded, and nothing remembers the fold.
- `lib/queue.ts` is the single home of «is it waiting and behind what»; `isQueued` believes
  `queue_position > 0`; `waitOf` only when something is truly ahead.
- A screen finds its own job by kind (`useJobRun`/`useOwnJobRun`), never by `currentJobId`.
  «Generar» shows the run of this visit plus any still live.
- Deleting or switching workspace never calls `client.clear()` (it destroys the session
  query); the same applies to `useAdopt`.
- One `--attention` per screen, on the thing to act on. A control and a report never share a
  line. Fold, never drop, and never fold the only copy of something. An (i) and visible text
  never say the same thing.
- No build time estimates anywhere, in any form.

## Specific screens

- **`/invite`** (`features/auth/AcceptInvite.tsx`, two ways through one link, decided
  2026-10-06). The lead line says who invites, where and as what («Te invita Ana Pérez a
  «Programación I» como alumno.»). With a session in the tab: «Entrar en «X» como luis»,
  «Unirme» (`/join`) and «No soy luis — salir»; a link that names no subject (an
  administrator's invitation to create an account) has nothing to join and says so. Without
  one: tabs «Crear mi cuenta» (the registration) and «Ya tengo cuenta» (only when the link
  names a subject): `useLoginAndJoin` logs in and joins in one press, and a login that works
  with a join that does not still adopts the session, so the screen turns into the open
  session's with the reason. A paused class link says so, with «Volver a comprobar», and lets
  nothing through. A join adopts the answer like a login (`useJoin`), toasts «Ya estás en…» or
  «Ya estabas en…» named from that answer, and goes to `/`. A student in no subject pastes
  the link instead (`NoWorkspace`), read by `invites.tokenFrom`, which mirrors
  `links.token_from`.
- «Mis asignaturas y ejercicios» (`/account/workspaces`, the account menu's entry): the
  subjects are the rows of ONE block and open alone, across the whole width; the button on a
  row that counts its exercises narrows the list into a column (its width animated,
  `--motion-overlay`) and opens beside it the account's own exercises there, each a block of
  its own on the ground (read with the row's slug as `X-Workspace`, no switch). Nothing opens
  by itself and nothing remembers the choice; in the column a row is a name, the permission
  and the count, the chosen one the sunk tint. Below `lg` the exercises take the list's
  place and a button leads back (user's request, 2026-10-04: unfolded under their subject,
  the exercises read as more subjects). «Generar más como este» in another subject switches
  into it first. It keeps every subject OF THE ACCOUNT'S
  OWN — the ones a membership row gives it — for an administrator like for anybody (user's
  decision, 2026-10-04): a subject reached only through the admin bypass (`as_admin` on
  `/api/workspaces`) has no row here; it is entered from the switcher and its exercises are
  read from «Administración → Asignaturas». The rows go in two groups (2026-10-06),
  «Donde doy clase» (editor, owner) and «Donde estudio» (viewer, and every paused
  membership), captioned only when both have rows; `/api/workspaces` lists a paused
  membership with `disabled: true`, and its row is named, dimmed, «Acceso desactivado», with
  nothing to open — not the subject, not its exercises — and the switcher leaves it out.
  Deleting a subject names who loses access (`PeopleWhoLoseAccess`: its active students and
  the other teachers), here and in the panel. Generate's
  «Mis ejercicios» tab shows the subject in use alone. The old routes (`/account/variants`,
  `/variants`) still redirect here.
- Graph: three columns (list, concept card, fixed-size graph card) plus a full-width
  relations block for the chosen concept. The canvas viewer (`features/kg/graph/`) lays units
  out as syllabus-ordered regions, relaxes concepts in a worker (Barnes-Hut, deterministic),
  caches layouts per structure, and picks detail by on-screen distance. Units open collapsed;
  the per-row «sirve de etiqueta» switch is the only place it is set and never moves the row.
  The syllabus no longer offers to decide the labels: that review heads the bank's
  collection (2026-10-08), and the build's own chain under the header is the descriptions'.
  The line over the list counts the concepts, the ones that work as a label and, once a bank
  exists, the ones with an exemplar (`/api/bank/coverage`, «N con ejemplo» with its (i)): it
  is a fact about the graph, so the bank's screen draws no coverage (user's request,
  2026-10-05). A student reads it as `SyllabusReader`: the header without a number and
  `GraphExplorer reading` under `StageGate.ReadingScope` (lock reason `"reading"`, which
  nothing lifts) — list, concept card, map and relations; no build, progress, correction or
  questionnaire, no column «sirve de etiqueta», no «sin descripción», and a line that counts
  the concepts and nothing else.
- Generate: numbered steps; after «¿De qué nivel?» and before the other decisions, «¿Qué
  partes lleva?» — one switch per `omittable` field of the type, all on at the start, drawn
  only when the type has one and never in the evaluation's form; a part switched off is
  not asked about in the step below and loses its pinned value; the curriculum box inside
  «¿Qué hay que practicar?» (no switch;
  in force when non-empty; marking a concept marks its prerequisites, and the closed list is
  what runs); prerequisites of targets are marked, never locked; exemplar-scope switch
  defaults to «Solo conceptos con ejemplos» each opening; model cards above the reasoning
  block (hidden with one model); a refused instruction locks the button until the text
  changes; after a run, «Variar el encargo actual» / «Empezar desde cero», both clearing the
  previous batch. Two tabs under the title (`components/TabStrip`, drawn as every tab):
  «Generar», where every visit opens, and «Mis ejercicios» with the count of the account's
  exercises in the subject in use (`useExerciseTotal`, a one-row page of the list's
  endpoint, refreshed as each item saves). The tab is `SubjectExercises` for that subject;
  its «Generar más como este» goes through `onGenerateMore`, filling the form and returning
  to «Generar», and is not offered while a batch is queued or running (`null`): the form
  never opens over a batch it did not ask for. «Generar» is hidden, never unmounted, so a
  run and the visit's results survive a tab switch; «Mis ejercicios» is mounted at its first
  opening, then hidden the same way and memoised, so it does not redraw with every frame of a
  run. The saved notice under the results opens the tab, and crossing tabs moves the focus
  to the tab opened.
- Evaluation: two blind cards at fixed height scrolling inside, «Ver completo» opens the
  reading dialog; after the reveal the same grid, collapsed, then the verdict band, then the
  rubric section. The screen reopens on the form, not the last session.
- Formulas render with KaTeX (`TeX`, tokenised before markdown, strict `$` rules,
  `throwOnError: false`); diagrams with Mermaid (lazy, painted in tokens, invalid ones show
  source and error). `lib/diagram.ts`'s `DRAWN` table decides which Mermaid kinds are drawn
  AND bundled (`web/vite/mermaid-subset.ts` fails the build if Mermaid's shape moves). One
  KaTeX version is forced via `pnpm-workspace.yaml`.
- `Progress`: total zero reads empty, unknown total sweeps (`barFill`).
- **There is no guide and no tutorial** (deleted 2026-10-16, D-225; hidden behind a flag
  since 2026-10-07). `/guide` and `/tutorial` are «not found» like any path with no route, a
  new account lands on `/`, and the server has none of them. Their text is in git history
  (before `5604d5c`).
## Client rules

- i18n: `es.ts` is the source, `en.ts` is typed against it (missing key = `tsc` error), `es`
  eager and `en` lazy. `pnpm check:i18n` catches untranslated literals. **Delete catalogue keys nobody reads** (prove it, delete from both, let `tsc`
  answer). Strings the server sends by stable key are translated client-side
  (`lib/names.ts`, `lib/raw.ts`, `lib/evaluator.ts`, `consumers/tutor/limit.ts`) with the server string
  as fallback.
- **A key read only inside `src/consumers/evaluation/` or only inside `src/consumers/tutor/` lives in that
  folder's `i18n/{es,en}.ts`**, same shape and typing; `i18n/index.ts` registers it
  (`registerCatalogue`: Spanish at once, the reader's language fetched), and every module
  core loads lazily from the folder imports it FIRST. Core wraps those `import()`s in
  `withCatalogues`, so an English reader never gets a first frame in Spanish. `Key` is the
  union, the functions' keys through `import type` only. A key read anywhere in core stays
  in `lib/i18n/`. `pnpm check:i18n` refuses a function's key read outside its folder, a key
  in no catalogue, a key in two, and a lazy module that does not register first.
- A screen's test draws it as markup (`renderToStaticMarkup`, node, its providers around
  it, `features/auth/AcceptInvite.test.ts`); `useLanguage` has a server snapshot for that.
- API payloads are read defensively: an older API must degrade the screen, never blank it.
  A panel that cannot load says so.
- `index.html` revalidates, `/assets` is immutable; a stale-chunk error reloads once.
- `pnpm check:ui`: no raw Tailwind scale sizes, no unlabelled control, no raw `<table>`.
- **What can be pressed shows the hand** (2026-10-13, the user's request): Tailwind 4 left
  buttons with the arrow, so a base rule in `index.css` gives `button`, `role="button"` and
  `role="tab"` the pointer, enabled ones only; a utility still overrides it.
- A `role="radiogroup"` of buttons takes its keyboard from `components/ui/radio.ts`
  (`useRadioGroup`: one tab stop, arrows choose and move the focus, Home/End).
- **`src/consumers/evaluation/` and `src/consumers/tutor/` reach a browser only through `import()`**, behind
  `useFeatures()` or inside the administrator's panel (whose reads ignore the mode): nothing
  outside them imports them statically (`import type` aside).
  `pnpm check:lazy` checks the sources and, after `pnpm build`, the chunk graph
  `vite/chunk-graph.ts` writes to `dist/.vite/chunks.json`; its comment stripping is a
  string-aware scanner with self-tests. `ApiError.code` is `X-Error-Code` and
  `ApiError.retryAfter` is `Retry-After` in seconds; a `feature_off` refetches the session
  (`main.tsx`), and a `not_member` or `membership_disabled` makes the tab leave the subject
  (`queries.leaveLostWorkspace`: forget the tab's slug, drop the instance's queries, land
  where `me` says).
- A vocabulary sweep is verified in the browser, not by a green suite.

## The run store

- The client's run store keeps 12 runs and lets go of finished ones first, never of a live
  one (`runStore.pruneRuns`): the socket carries every job of the workspace the account may
  see — the subject's builds and its own commissions, comparisons and tutor turns.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

**Interface**
- D-128 — The material is Atlas in clay: no white, two levels of depth, small things flat,
  careful edges; the palette measured; arm colours fixed; theme three-state.
- D-130 — One base for blocks, tables, lists, lists of sections, controls, choices and tabs.
- D-131, D-133, D-135, D-137, D-139, D-140 — The bar is the path: three numbered steps and the unnumbered doors open to
  the account, set apart by a rule, with no phase captions; the steps never fold; no
  dashboard; no rail. A student's bar draws «Temario» and «Banco de ejercicios» unnumbered.
- D-142 — Step 3 is two parts (types, then bank), one on screen, chosen from two cards at the
  top; «Paso 3 de 3 · Parte N de 2»; one part corrected at a time.
- D-144…D-147, D-149, D-151, D-153 — View and correct are two moments: «Modificar» and «Continuar» stand beside
  the title on every step; no «Aprobar»/«Reabrir»; no rebuild except for document drift;
  after the last step «Continuar» is «Generar ejercicios». The bank's collection closes the
  bank itself.
- D-155…D-159 — A queued job is not a running one. No time estimates, no «loading model»
  signal, no log on screen, no run drawer.
- D-160…D-164 — The generate screen belongs to the visit; its «Mis ejercicios» tab lists the
  subject in use; switching tabs keeps the run. Live feed of ten rows. Zero total ≠ unknown
  total. KaTeX for formulas.
- D-165, D-166, D-168 — The raw material is its own screen, one row per document; completeness
  is announced only by the finished origin's tick, the line over «Continuar» and step 1's
  state, which waits for every document read.
- D-170 — A raw document opens in step 1 as its original beside its transcription, page to
  page where it can; it opens to read; a page of the original keeps its white.
- D-172, D-173, D-175, D-176, D-177 — A control a teacher cannot decide is not offered: no
  screen edits `decided_by` or `embed_fields`; «Se elige al generar» (`omittable`) is the
  field's second row; the chosen option is the ink border over the ink tint.
- D-179, D-180 — No (i) beside a stage title; an (i) and visible text never say the same thing.
- D-181 — Settings show no «Por qué este valor»; an (i) only where needed.
- D-182 — Every tab of «Administración» is one list of its sections beside the one open; no
  tiles of totals; lists inside a block are ruled rows.
- D-183, D-184 — «Mis asignaturas y ejercicios» shows an account its own subjects and
  exercises only; the exercises open beside the list, never folded under their subject.
- D-186, D-187 — «Cuentas» is one table per kind of account, each a section, one search across
  them; no figure of what an account produced.
- D-189, D-190 — «Configuración» is one screen per stage; a shared setting is one value; an
  optional function's stage lives in that function's admin tab.
- D-191 — The mark is three equal squares (settled, attention, outline).
- D-192, D-193 — Every URL path is English. A refusal names the move out of it (`ChainGate`).
- D-194 — The exemplars profile is edited through the form alone.
