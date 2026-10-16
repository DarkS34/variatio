# AGENTS.md — `web/src/consumers/tutor/` — the tutor's screens

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Read `web/AGENTS.md` and `web/DESIGN.md` first. The tutor's server side is
`consumers/tutor/AGENTS.md`.

## The tutor's screen

- Tutor socrático (`web/src/consumers/tutor/`, `/tutor`): the conversation list beside the open
  conversation, both one fixed height (`PANEL_HEIGHT`) scrolling inside; a reply polled from
  the author's own route while `pending`, shown whole with its concept map when the server
  gave one (`ConceptMap`, redrawn 2026-10-08 at the user's request, in two rounds: a graph
  in a well, read left to right as the learning order — the known concepts as chips with a
  settled border, each curving into one point short of the concept and one arrow in; the
  concept an ink pill, with no unit under it; one line out opening into the later concepts
  as dashed chips; the prerequisite to review is the one coral chip (`ConceptChip
  tone="attention"`); what a cap left out is «y N más» under its column; every other
  relation a dotted branch with the graph's label on it, on the side its direction reads
  from — into the concept on the left, «Caso base se engloba en», the rest on the right,
  «se engloba en Abstracción». The lines are an SVG traced from the chips' boxes as laid
  out (`trace`, again on every resize and once the type loads; the geometry is
  `conceptMap.ts`'s, tested). Below the container's `@xl` the figure stands up — known
  above, later below, one arrow each — and the other relations go last, reached by a dotted
  rail down its left. No Mermaid, every colour a token), and nothing else under it (no
  places, no reader: 2026-10-08); a new turn scrolls the panel to its START, since a reply
  with a map is taller than the panel; the reply on its way is `Thinking`: the tutor's mark
  (`QuestionMark`, a question mark of the app's squares) written square by square (opacity
  only, so it stays on under reduced motion) beside one line of what happens and one of why
  the reply arrives whole — hollow and still, saying «En cola», while queued — with
  «Detener»; then «Pedir la respuesta otra vez». The box to write in (`Composer`) is two rows in one
  frame: the «Sobre» line — the concept chosen for the message (filled, removable), else the
  conversation's own focus (quiet), with the button that opens the picker and, with nothing
  to show, the word that choosing is optional — over the message and its send button; Enter
  sends, Shift+Enter breaks the line, and no character counter is drawn. With a concept
  chosen and the box empty, the placeholder is the commonest question («Explícame «…»») and
  Tab — or the key drawn beside it — writes it; Tab is taken only then. The two voices are two
  materials, each named above its turn: the student's message is a block of ink on the
  right, the tutor's reply open text on the left at a reading measure, with no rule beside
  it (2026-10-08). A reply is drawn in two registers (`Reply`): the explanation as body
  text, then its map when it has one, then the question(s) it CLOSES with — last, right over
  the box to answer in — a step larger in the heading's weight, with the tutor's mark beside
  it: the coral dot on the one question open (the last reply's, and only while no newer
  message waits for its own), settled grey on every question already answered. The cut
  is read off the prose by the client (`reply.splitReply`: the trailing blocks ending in a
  question mark, the first cut again by sentence so its lead-in stays with the explanation;
  never inside code, a formula or an emphasis) and never asked of the model. `TopicPicker` is the
  third concept picker of the app and the only single-pick one: a panel over the box with the
  numbered units down the left (each in its `domainColour`), the unit's concepts as
  `ConceptChip`s on the right and a search across both (`syllabus.searchSyllabus`); one click
  chooses and closes; keyboard: type to search, ↑↓ units, ←→ concepts (with something
  typed, ↑↓ results and ←→ the caret's), Enter, Esc. On a
  narrow screen the units are a scrolling row of tabs. The empty conversation lists the units
  as a numbered index, each row opening the picker on itself.
  A teacher (`can_edit`) gets a second tab, «Criterios de la asignatura»: a review of plain
  sentences (the subject's open, each unit folded; concepts and sources only when
  correcting), «Modificar», and a rebuild that asks first when there is a
  correction. The correction is the admin panel's list (`features/admin/Sections`) beside the
  part open (user's request, 2026-10-04: stacked down one page the parts could not be told
  apart): the three parts of the subject whole lead — «Para toda la asignatura», «Lo que el
  tutor nunca sugiere», «Consultas administrativas» — and one per unit follows under a
  caption (`SectionEntry.group`), numbered; a row counts what its part holds and its rows
  changed and not saved (`consumers/tutor/criteria.changes`, counted as sets); a criterion is a ruled
  row with no caption per control; the bar is the stage screens' (state, «Dejar de modificar»
  asking first when dirty, the save) and saves every part at once. «Trabajar con el tutor» on a saved exercise — in «Mis
  asignaturas y ejercicios» and Generate's «Mis ejercicios», and on a result card once its
  file exists, only with the tutor open — stashes the statement and the generation id
  (`lib/tutorDraft.ts`, in core because those screens are); on an exercise of the bank a
  student reads, its `bankId` instead (2026-10-14). The admin reads conversations
  from «Asignaturas» (`AdminConversations`).
