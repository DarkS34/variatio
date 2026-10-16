# AGENTS.md — `server/classroom/` — «Clase»

Read the root `AGENTS.md`, `server/AGENTS.md` and `server/auth/AGENTS.md` first (roles,
memberships and what a subject lets its students use are identity's). The closed decisions
are numbered in the root `DECISIONS.md`. The screen is `web/src/features/class/AGENTS.md`.

`members.py` holds the gestures on a person, `groups.py` the class's groups, `curriculum.py`
the course's progress and `activity.py` what the students do, counted. `routes/` holds
`/api/members` in four modules under one prefix — `people.py`, `groups.py`, `uses.py`,
`links.py` — and `/api/activity`; what the four share is `shared.py`, since no route module
imports another. A person's id travels as `{user_id:int}` and a group's as
`{group_id:int}`, so no fixed path of one module is read as an id of another, and mounting the
four one after the other answers every path as the single router did.

The three steps sit above the class in the server's layers: the bank shows an exercise to the
class's groups (`bank/marks.checked_groups`).

## People, links and groups

- **The people of a subject** (decided 2026-10-06): `members.py` holds the gestures —
  pause (`disable_member`), open again (`enable_member`), remove (`remove_member`), change a
  role (`change_role`) — and every door goes through them: `/api/members` (its router), the
  panel's membership routes (`POST /api/admin/accounts/{id}/memberships/{slug}/enable` opens a
  paused one), leaving a subject, and ending a course (`members.end_course`, the
  administrator's alone since 2026-10-07 at the user's request — it was the owner's —:
  `POST /api/admin/workspaces/{slug}/end-course`; every active student paused — `disable`,
  the default — or removed, the teachers stay, the class link is paused, the files stay). `members.people_of` counts a subject's
  people and `owners_of` names its active owners, for the listing and the panel. Closing a membership refuses taking the last
  active owner from people still active (`queries.would_orphan`, 409 `last_owner`; a
  subject with no owner to lose, or emptying, is not refused), moves the account's active
  subject elsewhere, cancels its jobs there, writes the row, COMMITS, then publishes
  `membership.closed` with `bus.publish_internal` (private with no author: no browser sees
  it) and logs `[asignatura] «a» desactivó/quitó a «b» en «slug»`. An open socket of that
  account closes with 4403 on it (`ws._closes`); a handshake refused for its subject is 4403
  too (`deps.authenticate_socket` returns the close code), a missing session 4401. A paused
  membership (`memberships.disabled_at`) keeps role, `via` and date, grants nothing (403
  `membership_disabled` in `access_for`), and counts in no reading but the roster:
  `memberships_for`/`members_of` leave it out unless `include_disabled`; the delete-the-tree
  decisions count it (its files are there). An owner is never paused (409
  `owner_disabled`); nobody pauses or removes themselves there (409 `self`; leaving is
  `DELETE /api/workspaces/{slug}/membership`); a teacher acts on students and the owner on
  teachers (`role_too_low`). Leaving with others inside is `remove_member`.
- The username is the identity; `users.email` is an optional delivery detail, shown only when
  mail is configured (`mail_configured` on `/api/auth/me`). No «forgot password» link on the
  login screen; admins hand out reset links. No password generator anywhere.
- `users.evaluator_profile` authorises nothing inside a subject: the membership does.
- **A teacher's links** (decided 2026-10-06; `/api/members`): a subject has at most ONE live
  class link per destination (`class_links`, revoked = dead; the rule is code, not an index;
  the destinations are the class and, since 2026-10-14, each of its groups:
  `class_links.group_id`, `queries.live_class_link(session, workspace_id, group_id)`) — seats (40 by
  default, `CLASS_LINK_MAX_SEATS` 300), a required expiry (30 days by default, at most
  `TEACHER_LINK_MAX_DAYS` 180), a pause — minted sealed like an invitation
  (`links.mint_class_link`) and renewed by revoking it; its seats never drop below those
  taken. A seat is taken by ONE conditional UPDATE (`queries.reserve_seat`: free seat, not
  paused, not revoked, not expired) AFTER the checks and the password hash, so the row lock is
  short; an account that cannot be created rolls the seat back with it. `/accept` takes both
  kinds (a class link: bucket `accept_class`, keyed by the link, a student's account, a
  `viewer` membership `via=class_link` with `invited_by` its minter), refusing a full link
  `class_link_full` and a paused one `class_link_paused`; a dead link of either kind is one
  404 sentence (`DEAD_LINK`). `/join` lets an existing account in with either kind (bucket
  `join`): a paused membership is refused first and spends nothing; a personal invitation is
  spent even when the account was in; the higher role wins; the profile never moves. The
  preview says `kind`, `inviter` and the subject, never the seats left. A teacher mints the
  subject's personal invitations (one per name, the name as alias; a teacher's — `editor`,
  profile teacher — only by an owner; no `features`; bucket `teacher_invite` per link), reads
  their links again (logged) and deletes them; another subject's are 404. Where the
  installation sends mail (`mail_configured`), a line may be «Nombre <correo>» (`emails`
  beside `names`, `lib/invites.recipientsOf`): the link is mailed, the answer says `sent` per
  invitation, and the address is kept nowhere — not in the row, not in the log
  (`mail.send(shown_as=…)`); without mail an address is a 422. The administrator
  lists every live class link, pauses and retires one (`/api/admin/class-links`), from the
  «Enlaces de clase» block under the table of «Asignaturas» («Pausar»/«Reanudar», «Revocar»
  asked first); their seats and dates stay the teachers'.
  `system class-link --workspace S [--seats N] [--days D] [--renew]` prints or mints it.
- **The groups of a class** (decided 2026-10-14; migration 0022, `groups.py`): parts
  of a subject's class its teachers treat apart, and **with a group they do what they do with
  the class**. `class_groups` (unique name per subject) and `class_group_members`, whose
  `membership_id` is unique: a student is in ONE group at most, for now (lifting it is
  dropping that constraint and deciding which group wins); a teacher is in none (409
  `not_a_student`). A paused student keeps their group; a removed one loses it with the
  membership. Routes under `/api/members/groups` (`auth.EDIT`: list, create, rename, delete —
  its students stay with no group and its live link dies); moving is the `group` action of
  `POST /api/members/bulk` (`group: null` takes out), refusals person by person; a member's
  view says `group`. Each of the class's readings and gestures takes `?group=` (another
  subject's group is a 404): the tools (`GET`/`PATCH /api/members/uses?group=`, a group's
  `generate`/`tutor`/`chat` being `true`, `false` or `null` = as the subject), the link and
  the invitations (`class-link?group=`, `invites.group_id`: who comes in through them lands
  in the group, `groups.place_on_entry`, at `/accept` and `/join`), the progress
  (*Curriculum*, below) and the activity (*Class activity*, below). `features.refusal` reads the
  administrator's mode, then the student's group's switch when it says something, then the
  subject's, the refusal naming which closed it. `members.end_course` pauses every live link
  of the subject, the groups' included. The administrator's «Enlaces de clase» names each
  link's group.

## Curriculum (`curriculum.py`)

Host state (`artifacts/.curriculum.json`), validated against the graph on read. **Absent
falls back to the file, `[]` means no restriction.** `resolve()` closes the list in force
downward (prerequisites included) and the row records what ran. The file is the subject's
«Avance de la asignatura» (decided 2026-10-06), set by its teachers in «Clase» (`PUT
/api/kg/curriculum`, closed under prerequisites as it is saved) and tinted on the syllabus.
**It bounds nobody** (the user's decision, 2026-10-07: a student who wants to run ahead of
the class may): a commission's own list replaces it, a student's as a teacher's. The generate
form starts with no curriculum and offers the progress as one press, «Usar lo visto en clase»
(`GenerateForm.classProgress`), drawn only when the progress holds something and disabled
while it is what is ticked; it ticks the progress's frontier (`prerequisites.frontier`), so
the selector marks the rest instead of drawing every prerequisite as a pick. `GenerateForm`'s
`assumedKnown`/`notYetTaught` mirror `variatio.assumed_known`/`forbidden` — edit the Python
first. **A group may follow its own** (2026-10-14): `class_groups.progress`, null while it
follows the subject's, validated on read the same way (`curriculum.of_group`, which says
`own`). `GET`/`PUT /api/kg/curriculum` take `group` (`follow_subject` hands it back); a
student reads their group's when it has its own, so «Usar lo visto en clase» offers it; the
activity's «sin practicar» reads the scope's.

## Class activity (`activity.py`)

What a subject's students do, for its teachers (the user's request and decision, 2026-10-07):
`/api/activity` (`auth.EDIT`; a student reads nobody's, their own included). **The week is
the unit**: ISO weeks, Monday to Sunday, UTC (`server/core/daily.py`); a past week is closed —
every message and exercise is dated, so its figures do not move — and the present one is open.
The history is the strip of weeks from the first with activity to now, an empty week kept.
`?student=<id>` narrows to one student (active or paused; anybody else is 404); a removed
student counts for nothing, a teacher's own files are not the class's. `?group=<id>` narrows
the class to one of its groups (2026-10-14): every figure, finding, week and «Quién …» row is
counted over its students, and «de la clase» reads «del grupo». A group's digest is its own
(`POST …/digest` with `group`, the job reading that group's messages alone, one per week and
group at a time, `analytics/digest/<week>.group-<id>.json`); without one the reading shows the
class's cut to the group's students, as for one student.

- **Counted by code, never read**: of a conversation, each student turn's date, its reply's
  kind (`on_subject` for theory/exercise/attempt/solution), the concept (chosen, else the
  reply's first focus) and `sent_back`; of an exercise, its date, type, level (the workspace's
  difficulty field, `locale.difficulty`) and concepts, and whether a conversation was opened on
  it. The tutor's half comes through `activity.TUTOR_READER`, which `consumers.tutor.api.install` sets
  (the server never opens the tutor's files); every file goes through `activity.cached`, keyed
  by modification time and size.
- **Findings** are typed by the server, each of one page (`area`: `tutor` — `asked`,
  `solutions`, and for one student `topic`, `reviewed` — or `exercises` — `unpractised`, with
  the course's progress only, and for one student `practised`; `idle`, `trend` and, for one
  student, `quiet` are counted in each area apart, at most `MAX_FINDINGS` per area), and
  worded by the client (`lib/activity.sayFindings`, `findingsIn`; a finding with no area is
  placed by its kind). A student row carries `message_days` and `exercise_days` beside their
  sum `days`; the first a teacher can act on is the
  screen's one `--attention`. Thresholds (`MIN_ASKERS` 3, `SOLUTION_SHARE` 0.4 over
  `MIN_SOLUTION_MESSAGES` 5) are placeholders until the pilot measures them.
- **The digest is the teacher's to ask for**, never written on its own:
  `POST /api/activity/weeks/{week}/digest` queues the tutor's `activity_digest` job (class C,
  private to its author, not behind the tutor's function — a teacher reads their class's
  whether or not the tutor is open to them; one per week at a time, 409 `digest_busy`; at
  least `DIGEST_MIN_MESSAGES` 10 messages about the subject). Its parameter is the week; it
  groups the week's messages by concept (the `tutor.digest_max_concepts` most asked, each
  with its latest `tutor.digest_max_messages`), reads their texts inside the job, and asks the
  `tutor_digest` call (`tutor.models.digest`, empty = the classification's model) for at most
  three themes per concept, one sentence of 20 words at most, with the numbers of the messages
  they cover. **Paraphrase only**: a theme that copies more than 8 running words of a message,
  names a student (whole name, username, or a part of 4 letters or more), is too long or covers
  nothing is asked again once with a note, then dropped (`consumers/tutor/digest.clean_themes`). Only
  step events cross the stream, the log says counts, and the file —
  `<workspace>/analytics/digest/<week>.json` — keeps the themes and REFERENCES to the messages
  (author, conversation, turn), never a message. One digest per week, of the class: a theme's
  figures are counted from its references over who is of the class now, and a student's
  reading is the class's digest cut to the themes their messages fall under, with how many
  are theirs.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in the root
`DECISIONS.md`. Do not reverse one without the user's explicit request.

- D-098, D-099 — A class may have groups, and with a group its teachers do what they do with
  the class; a student is in one group at most, teachers in none. One live class link per
  destination.
- D-105, D-107 — The administrator keeps every power; a teacher also brings their class in
  (class link, personal invitations; an owner invites teachers) and pauses, opens and removes
  its students. A subject with people keeps an active owner; pausing is reversible, removing
  is not; neither moves what a person made.
