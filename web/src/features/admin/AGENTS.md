# AGENTS.md — `web/src/features/admin/` — «Administración»

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Read `web/AGENTS.md` and `web/DESIGN.md` first.

## «Administración»

- «Administración» lives in the account menu (soft red), before «Tema», before «Salir».
  Six tabs: «Motor», «Configuración», «Cuentas», «Asignaturas», then, ruled off, one per
  optional function in its own tone — «Evaluaciones» (`--evaluation`) and «Tutor»
  (`--tutor`), drawn for the administrator whatever the function's mode. **Every tab is one
  list of its sections beside the section open** (`components/Sections.tsx`, user's
  request of 2026-10-04: «Motor» had a board of cells, «Configuración» a column of stages
  and the functions' tabs stacked everything down one page). A row of the list is a 16 px
  mark — an icon, or `NumberMark` where the list is an order (steps, units); «Motor» shows its
  parts' icons, its state in the line, since 2026-10-07 — a name and
  ONE line of state, drawn even while it loads so the row never changes height (how many accounts, a part of the engine in a word, who may use a
  function, how many settings) plus the count of what is changed there and not saved; the
  list is the tab's summary, so no row of total tiles sits above the tabs. The section opens
  under `SectionHeader` (name, one sentence, the section's one action on the name's line) as
  ONE column of blocks, readings first and settings under them. A list inside a block is
  rows parted by rules, never a frame per row or around a table (`.rows` in `index.css`;
  `SETTING_LIST`). A tab with one section («Asignaturas») has no list; its table names each
  subject's owners and counts its students (2026-10-06), and a subject with no owner reads
  «Sin propietario» with «Elegir propietario»: one of its people, or another teacher's
  account, made owner through the panel's grant. A row's calendar icon ends its course
  (`EndCourseDialog`, drawn off where the subject has no student): pause every student (the
  default, undone by opening them) or remove them, confirmed in one dialog by typing the
  subject's name as written, as deleting a subject is; destructive, never `--attention`. Below `lg` the list
  lies down and scrolls sideways. The maintenance switch is in the header, beside the
  title: one line while the installation is open, a red block across the page while it is
  closed; it is no tab and no section. A function's tab has three sections — «Permisos de
  uso», «Analíticas» («Evaluaciones» only) and «Configuración» — and `AdminScreen` holds
  which is open, because a folded link opens one from another tab.
  «Permisos de uso» is
  `features/admin/FeatureAccess.tsx` (a radio group «Nadie» / «Todas las cuentas» /
  «Cuentas elegidas», the accounts ticked under the last one with the viewer's own row
  marked, a local draft and one «Guardar los cambios»; the ticks stay on screen, dimmed,
  under another mode because the server keeps the list; one sentence states the SAVED state,
  one line says the administrator is not exempt; «Por asignatura» ticks or unticks at once
  every account in a subject now, `accounts.accountsIn`, paused memberships left out). **What a
  chosen subject covers is drawn in the accounts** (user's request, 2026-10-19: ticking a
  subject left its students unticked, and an account that used the function read as one that
  did not): an account in a subject of the draft's «Asignaturas elegidas»
  (`accounts.coveredBy`) has its box ticked and LOCKED and a badge «Por <asignatura>» («Por N
  asignaturas»), because unticking it would take nothing away; its own tick, if any, can
  still be taken off. «Cuentas elegidas» says that a ticked account uses the function in all its
  subjects, each chosen subject counts its accounts, the count says how many ticks are a
  subject's, and one line says how to leave somebody out. «Analíticas» is the evaluation's reading
  (lazy); «Configuración» is the function's stage settings (`ConfigTab.StageSettings`, its
  own save bar over the same values; `tutor.daily_messages` is there). A folded link to
  another stage opens «Configuración» on it: `AdminScreen` owns the tab, the open stage and
  the ONE draft of the stages' settings (`useStagesDraft`), so a change left pending follows
  the link and any of the three save bars saves it. An invitation's form (new, recovered, edited) ticks the functions whose list its
  holder joins at registration («Funciones»), and each row shows them as badges in the
  functions' tones. The form opens on «Perfil de la cuenta» — «Docente» / «Alumno», a radio
  group with NEITHER marked, the button waiting until one is — and each row shows the profile
  as a badge. «Cuentas» has one section per kind of account, then «Invitaciones», then, ruled off,
  «Acceso» (`AccessSection`: the school networks, a draft saved with «Guardar los cambios»,
  read-only when the environment sets them). The accounts are ONE TABLE PER
  KIND (user's request, 2026-10-04; `features/admin/accounts.ts`, `groupOf`): «Docentes» and «Alumnos» by
  `evaluator_profile` (no «Sin perfil» since 2026-10-06: migration 0017 left none, and an older
  API's NULL reads as a student's), «Administradores», and
  «Desactivadas» — a deactivated account is that first, an administrator before a profile.
  Each kind is a row of the list with its count, drawn only when such an account exists, and
  opens its table alone (same day: stacked down one page, the students sat under every
  teacher). The search over the list reads the name and the username (`matchesAccount`) and
  draws the same tables with the matching rows alone, across every kind.
  Same columns and widths on each: the account, its subjects one per line (name, then the
  permission in a column of its own, the widest first), the date, and «Gestionar», which
  opens the memberships and the account's controls under the row; a membership a teacher
  paused reads «Desactivada» with «Activar» in place of the role. The profile is a line
  there, «Perfil: …», with one button, «Hacer docente» (confirmed), on an account that is not
  a teacher; a teacher's has no control, since the profile only climbs. No count of exercises,
  no comparisons and no «ver sus sesiones» there: what an account evaluated is read in
  «Evaluaciones».
  «Motor» tab: **one section per part of the engine** — «General», «Local», and
  «Remoto» only when the engine has that half — each row its state in a word (on «General»
  the queue's line, since its word is the engine chosen); the tab opens on the part that
  needs somebody, else on «General». The readings
  are `features/admin/engineState.ts`, shared by the rows and the cards' badges. «General»
  leads with the choice of engine («Solo local» / «Híbrido», `engine.name`), then the queue
  and its order («Orden de la cola», `queue.*`),
  the connection to Ollama (direct when no `OLLAMA_SSH_HOST` is named — never drawn as a
  tunnel left unconfigured — else the SSH tunnel) and the warm contexts; «Local» is the GPU and the models on ITS disk (a
  remote model has no row there) with its cap of background jobs; «Remoto» is the quota. A setting the panel cannot change
  (environment, or `editable=False`) is not drawn. Models are never downloaded from the
  panel (a build pulls what it lacks). `CEREBRAS_MODELS` is ticked from the catalogue plus
  what the engine already lists, never typed. The four Cerebras ceilings are one group named
  and ordered as the four meters, each capped at the registry's `maximum` (the account's
  quota). The queue card is one list of three moments — waiting (dimmed, hollow mark), running (ink)
  and the last 30 finished (settled; red where it failed), which the admin may clear: clearing
  moves a window (`POST /api/admin/jobs/history/clear`), it never deletes a job. No database card. One save bar for the tab; a part's row counts
  its unsaved changes; the guardrail and embedder models are read-only. «Configuración» is **one section per stage**, named and
  numbered as the bar (`features/admin/stages.ts` reads `lib/steps.ts`): the stage's calls
  down the page, each node with model, reasoning and sampling and its own settings under it;
  then «General de la etapa», «Común a todas las etapas», and folded what it reads of
  another stage's — the same value, unfolded on its owner's screen. The search sits over
  the list and «Recargar desde el fichero» under it. Its list holds the
  product's stages only: an optional function's stage (`ConfigStage.feature`) is drawn in
  that function's tab, and «Configuración»'s search still finds and edits its settings.
- A setting's measured `doc` stays in the registry and never leaves the API. A row carries at
  most one (i), and only where its name does not say what it controls or a change has a
  consequence nobody would guess: `features/admin/hints.ts` maps the registry key to
  `cfg.hint.<key>`; a key missing there draws nothing.
