# AGENTS.md — `web/src/landing/` — the landing and the demo

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Read `web/AGENTS.md` and `web/DESIGN.md` first.

## The landing (`web/src/landing/`)

What a visitor WITHOUT a session sees at `/` (the user's decision, 2026-10-12): what the
system is, how it works, a demo of the application, and the way in — registration closed,
entry by invitation, «Entrar» leading to the login form at `/login` (`AuthGate.LOGIN_PATH`;
with a session `/login` redirects to `/`, and the login form has «Volver a la portada»).
With a session `/` is still the application's redirect to the current step: no dashboard.
A module of its own, like `consumers/evaluation/` and `consumers/tutor/`: its strings in `landing/i18n/`
(`landing.*`), fetched only by a visitor (`check:lazy` lists it in `LAZY`), in Spanish and
English. The names the application already has (steps, door, phases) are the core's keys.

- **`/` is decided by ONE reading, never a live query** (`AuthGate.Front`): the session and
  the door are asked once before anything mounts; a 401 with the door open draws the
  landing, anything else hands over to `Guarded` as before, and an account the cache
  already knows skips the reading. A live session query beside the landing would be
  answered by the demo's server (below) and log the visitor in as its teacher.
- **The header's links** (`landing/sectionNav.ts`, the user's report of 2026-10-12: they
  "scrolled wrong" and the last never arrived): a link brings its section's HEAD to rest
  24 px under the header (`scroll-mt-[5.5rem]` = `HEADER_PX` + `REST_PX`); the last linked
  section (the demo) and what follows it fill a window at least, the room they lack given
  to the FOOTER (measured; given to the section, it opened a hole between the demo and the
  band on a tall window), so it arrives like the rest; the mark is the last section past a
  reading line, or the last of all at the page's foot (`sectionAt`, tested), and it is
  HELD on the link pressed until the smooth scroll ends. A page opened on `/#demo` goes
  there once laid out and again once the type has loaded.
- **The page** (redrawn on 2026-10-13 at the user's request: five sections of one weight,
  lorem ipsum in the hero and the application's names in «Cómo funciona» read as nothing in
  particular): a sticky header — the lockup, two anchors («Cómo funciona», «Demo») that
  mark the section in view, the language as a quiet switch (a globe and two codes over
  `localeStore`, which the demo follows) set apart by a rule from «Entrar», the one filled
  button — then four parts with no rule between them, each opened by its title and at most
  one line, with no eyebrow but the hero's («Para docentes»):
  - the hero: «Tus apuntes, convertidos en ejercicios nuevos.», one coral button, «Probar
    la demo» (the page's one `--attention`), three facts, and its picture — the whole system
    on an INVENTED example (the user's choice: real-looking content, written for the page):
    a passage of the notes, the concept in the syllabus after the ones already covered, and
    the new exercise, in three subjects far apart (Programación, Enfermería, Lengua), one
    tab each (`TabStrip` in a hairline frame, so the three read as a switch; nothing turns
    by itself). Every example stays mounted in one cell, so the block is as tall as the
    longest and a tab never moves the page; a change fades the old one out and the new one
    in, one after the other (remounted, its parts came back one by one and the block
    flickered: the user's report, 2026-10-13). The arrows between the parts are bare: in a
    round tint they read as buttons.
  - «Cómo funciona»: a teacher's three moves in plain verbs, flat on the ground, numbered
    and joined by a rule — never the application's names for its steps, which a visitor
    does not know yet — under one line saying that a prepared subject serves the whole
    class (the user's request: the class is mentioned, not presented; no block for the
    students or the tutor).
  - the demo, presented as before (below); its picture of the application opens the demo
    too, for the pointer only (out of the tab order, «Abrir la demo» beside it being the
    same move), and says so under the pointer.
  - the way in: the page's one band of ink, «¿Tienes una invitación?» with «Entrar» in the
    band's inverse. No contact button (the user's decision: they are reached elsewhere).
  The footer is the lockup and the licence, nothing else (the user's request, 2026-10-13:
  no line about the master's thesis). Only the picture and the demo stand out of the
  ground. Copy is one line per idea, by the
  user's request ("demasiado texto"), and claims nothing an installation may not keep:
  «en tu propio servidor» left with the redesign, since the hybrid engine sends text out.
- **The demo is a page of its own, `/demo`** (`landing/DemoPage`; the user's request,
  2026-10-12: framed inside the landing it was too small to read). Public — `AuthGate`
  answers it before the session is read, so no live query of the page meets the demo's
  transport — and the application fills the window under one slim sunk bar that is the
  demo's: «Portada», its name, «Cargando los documentos de ejemplo…» while they arrive (or
  «Añadir documentos de ejemplo» should the visitor delete them), «Reiniciar», «Ir a
  «Generar ejercicios»», the language.
  `/demo?start=generate` opens it with the construction closed. The router's path is the
  address without its query (`router.pathOf`): with it, the link matched no route and
  landed on the login form (the user's report, 2026-10-13). The landing's «Demo»
  section only presents it: three lines, the two ways in, and a glimpse of the bar drawn
  with the application's own `StepCounter`.
- **The demo draws the REAL screens over a server in memory** (the user's requirement,
  2026-10-12: faithful to the real design, never a drawing of it). `landing/demo/DemoFrame`,
  sized by the page that holds it,
  mounts `App` — the shell, the bar, the three steps and «Generar ejercicios» — under its
  own `QueryClient`, `lib/router.MemoryRouterProvider`, toasts and confirmations, and swaps
  three things of the client while it is on screen, all put back when it leaves and on
  `pagehide`: the transport (`lib/api.setTransport`, which the upload goes through too),
  the run store's source (`runStore.drive`: no socket; events come from `ingest`) and the
  tab's workspace (`workspaceStore`). Nothing reaches the wire. The swap is a layout effect
  and the children mount after it; a world is made per mount and «Reiniciar» is a new key.
- **The frame contains the application**: its box carries a transform (the containing
  block of every `fixed` thing inside), and full-screen overlays — `Dialog`, the
  `ConceptSelector` — portal into `ui/overlay.OverlayRoot` when one is provided, else
  `document.body`. Hints and a unit's menu keep `document.body`: they are placed in window
  coordinates. A same-origin `iframe` would need the server to allow a frame, and it refuses
  every one (`frame-ancestors 'none'`, `X-Frame-Options: DENY`): the demo leaves that as is.
- `landing/demo/world.ts` is the state and every answer (`/api/*` shapes read off a real
  installation on 2026-10-12, `landing/demo/api.ts` the route table), `jobs.ts` the
  simulated jobs — the same events, steps and payloads as the handlers and the builders,
  seconds instead of minutes — and `data/*.json` the sample subject (lorem ipsum, by the
  user's request; JSON so the copy lint does not read it) plus the server's own sentences
  and labels (`server.json`, `steps.json`, `plans.json`). Two presets: `fresh`, a new
  subject — both origins EMPTY and nothing built, so the bar opens on step 1 «Te toca
  ahora» — and `ready` (the construction closed, the door open, every document read). **The sample documents come in by themselves** (`world.arrive`, the user's request
  of 2026-10-12: «los usuarios solo tienen que esperar»): half a second after the frame
  mounts, one every 250 ms; once per world, finished after a stop half way. Step 1 stays
  «Te toca ahora» until the visitor presses «Procesarlos todos ahora» (the user's choice) and
  the reading ends, as in the application. Should the
  visitor delete them, the demo's bar offers them again (`world.addSamples`), outside the
  application, which stays as it is; a file the visitor drops on an origin works too and
  never leaves the browser. The world tells its listeners (`world.subscribe`) of every
  change of the documents, and the frame reads the application's queries again on it.
- **The pace is one table** (`jobs.ts` `PACE`, milliseconds per job, spread over its ticks
  by `every`): a visitor waits seconds — the user's request, the same day: «acelera las
  cargas, es una demo». Measured then: a slot's reading 1.2 s, the syllabus with its
  descriptions 2.3 s, the types 1.0 s, the bank's whole collection 1.9 s, three exercises
  1.9 s (from 5.1, 11.6, 3.6, 9.5 and 13.2 s); `pace.test.ts` pins upper bounds. A job starts
  120 ms after it is queued and every answer takes 20 ms (`api.ts` `LATENCY`).
- The features are closed in the demo's session (no tutor, no evaluation), and so is the
  class page (`features.class: false`, read by `featuresOf` — only a literal `false` closes
  it and no server sends one: «Mi clase» leaves the menu, `/class` is «not found», and the
  demo's listing sends no `people`, so a subject row offers no «Clase · N alumnos»; the
  user's request, 2026-10-13). A route the demo does not answer is a 404, as an older API
  would be.
