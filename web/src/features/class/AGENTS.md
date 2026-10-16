# AGENTS.md — `web/src/features/class/` — «Clase»

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Read `web/AGENTS.md` and `web/DESIGN.md` first. The server's rules for people, links and groups
are in `server/auth/AGENTS.md`; for the curriculum and the activity, in `server/AGENTS.md`.

## The activity screen of «Clase»

- **The screen** (`features/class/ActivitySection.tsx`, `activity/*`): two pages of «Clase»
  (their lead under the title AND the scope, on one line where the window allows:
  `SectionHeader wide`),
  one for each thing a student uses (`ActivityView`; user's requests, 2026-10-07: one page
  stacked five blocks, then a page of the week in general read as neither): «Ejercicios
  generados», «Tutor socrático» (only where the tutor is installed) and «Chat libre» (only
  where the chat is: its two figures, its findings and «Quién usa el chat»; nothing of what it
  was asked). Both carry the scope
  in the header and the strip of weeks (`WeekStrip`, counting the page's own figure; a dot
  for a digest on the tutor's page; an empty week dimmed; arrows from week to week), both
  held by `ClassScreen` so they survive a move between the pages, and answer three questions
  in one order: how the week went («Lo importante»: three key figures — how many, with the
  week before; how many students of the class, or for one student the class's median; the
  exercises taken to the tutor, or the messages asking for the solution — then the page's
  findings), what it was about («Qué practican»: by unit of the syllabus, a unit not covered
  yet dashed, then by type and level in the type's own scale; «Qué preguntan»: the digest by
  unit and concept, or the most asked concepts until it exists, and «Cómo preguntan»: what
  they ask for, where the tutor sent them back), and who did it («Quién genera», «Quién usa
  el tutor»: the least first, seven day squares of that page's measure; the class's scope
  only). The design was the user's to choose in rounds; a change to it starts with
  screenshots.

## «Clase»

- **«Clase»** (`/class`, `features/class/ClassScreen.tsx`; decided 2026-10-06): the class of
  the subject in use, its teachers' alone (a student gets «not found», and `/api/members` is
  `auth.EDIT`). Entered from the account menu's «Mi clase», above «Mis asignaturas y
  ejercicios», where the session's role is a teacher's, and from each subject of «Mis
  asignaturas» the account teaches, as «Clase · N alumnos» (`GET /api/workspaces` counts
  `people` — students, paused, teachers — on those rows), switching into it first. Drawn as a
  panel tab (`admin/Sections`): the list of its sections beside the one open, each section
  one subject of its own so a page is read without scrolling past another (user's requests,
  2026-10-07), the subject's name read off the TAB's slug, never the session's `active` flag.
  The list goes in three groups captioned with `SectionEntry.group`, in this order:
  «Miembros» («Alumnos», «Grupos» — drawn where the API sends `groups` —, «Docentes»,
  «Invitar»), «Actividad» («Ejercicios generados», «Tutor socrático» and «Chat libre» — each
  of the last two only where it is installed) and «Curso» («Avance de la
  asignatura», «Funcionalidades permitidas»). Ending a course is not here: it is the
  administrator's, from «Administración → Asignaturas». It opens
  on «Alumnos», or on «Invitar» while there is no student. «Alumnos», «Docentes» and the
  unused invitations draw people the same way (`PersonRow.tsx`, `PeopleTable`: the panel's
  flat table — who, how they came in, since when — one 44 px row each, the gestures as icons
  on hover or focus; user's requests, 2026-10-07). «Alumnos» (`lib/members.ts`): a filter «Activos» /
  «Desactivados» (no «Todos», user's request 2026-10-07), a search over name and username,
  and the students in that table, its head's box ticking the list and, over the ticked ones,
  the head turned into the filter's gesture («Desactivar (n)» or «Activar (n)») and «Quitar (n)»; each row carries the
  same two as icons on hover or focus (a table left most of its width empty) — each
  confirmed naming how many;
  removing is its own dialog — final, offering «Desactivar en su lugar» — and every gesture
  goes through `POST /api/members/bulk`, refusals toasted person by person. A tab whose
  subject closes on its account (`not_member`, `membership_disabled`, or the stream closed
  with 4403: `runStore.lost`) leaves it through `queries.leaveLostWorkspace`. «Invitar»
  (`features/class/InviteSection.tsx`; its row reads the general invitation's state and how
  many personal ones are unused) is one page of two blocks, drawn anew on 2026-10-07 at the
  user's request. «Invitación general» is the class link, its state a badge on the title's
  line: without one, seats and a date and «Crear el enlace» in a well; with one, its QR code
  small on the left — pressed, «Proyectar» opens it big —, a bar of the seats used and free,
  the expiry, the link (read once per visit, a logged read; a mint's answer seeds it) with
  «Copiar», and under a rule a quiet row of its gestures; the big dialog to project: `lib/qr.ts` draws ONE SVG path with `qrcode-generator` — MIT, no
  dependencies, in the class screen's chunk alone — medium correction and a quiet zone of
  four, in `--qr`), «Pausar»/«Reanudar», «Renovar el enlace» (asked first: the current link
  stops, whoever came in stays; same seats, same date unless gone), «Cambiar plazas o
  caducidad» (only what moved is sent) and «Borrar el enlace» (asked first;
  `DELETE /api/members/class-link`, no link after it, whoever came in stays). «Invitaciones
  personales» is the list of the ones nobody has used yet, drawn as the people are, with
  «Nuevas invitaciones» on the title's line, which opens the form in a dialog: one name per
  line
  (`invites.namesOf`, twins kept), a date, «Crear N invitaciones» — validated on press, at
  most 50, 180 days ahead at most (the server's constants mirrored in `lib/invites.ts`) — and
  the dialog then shows what was minted until it is closed: a link per name, «Copiar todo»
  (alias TAB link) and
  «Descargar CSV» (`nombre,enlace,caduca`, `lib/csv.ts`: a cell opening `= + - @` or a control
  character gets the apostrophe of `server/csv_safe.py`, numbers exempt, RFC quoting, a BOM).
  An owner chooses «Alumnos» or «Docentes» over the names (a teacher's invitation, `editor`,
  gives a teacher's account), and a teacher's invitation wears a «Docente» badge.
  On an unused one, the copy icon reads the link and copies it in the SAME press (a
  `ClipboardItem` holding the promise), and where the browser refuses, the link opens under
  the row; the bin deletes it, asked first. «Actividad» is `ActivitySection`, see *Class
  activity*; a student row's icon opens «Ejercicios generados» on that student. «Docentes» (`TeachersSection`: who teaches it, owners first, every account's to read; an
  owner's gestures, as icons on the row and each asked first — «Hacer propietario», «Pasar a docente», «Activar» a
  paused teacher, «Quitar», and «Ceder la propiedad»: the other made owner FIRST, then the
  owner's own role lowered, two `PATCH /api/members/{id}`, so the subject has an owner at
  every moment; the session is read again after). «Avance de la asignatura»
  (`ProgressSection`: how many concepts are covered, unit by unit in the syllabus' order —
  `lib/courseProgress.ts` — the selector of a commission's coverage to change it, saved on
  its confirm, and «Borrar el avance», asked first) and «Funcionalidades permitidas»
  (`UsesSection`: switches that act at once — generating, the tutor and, since 2026-10-15, the
  chat, drawn off until a teacher opens it; the two «Curso» blocks are drawn alike,
  ruled rows of a name, one line under it and its control on the right; the tutor's drawn wherever the tutor is
  installed, off and still with the reason until the administrator offers it).
  **Groups in «Clase»** (2026-10-14): every section that acts on the class — «Alumnos»,
  «Invitar», the two activity pages, «Avance de la asignatura», «Funcionalidades
  permitidas» — carries a scope in its header (`GroupScope`: «Toda la clase» and the groups
  as tabs up to three, a select past them; nothing while the class has none), held by
  `ClassScreen` so it survives a move between sections, and every reading of those sections
  is the scope's. «Grupos» lists them with their active students and «Nuevo grupo» on the
  title's line, renaming and deleting (asked first) as row icons; a group's row opens
  «Alumnos» on it. «Alumnos» names a student's group as a badge in the class's scope, moves
  one or the ticked ones with «Cambiar de grupo» (`MoveDialog`: «Sin grupo» or a group).
  A group's tools are three pills each, «Como la asignatura» / «Abierto» / «Cerrado», with
  what the subject says under the name; its progress says whether it follows the subject's,
  with «Darle su propio avance» or the way back to the subject's.
