# AGENTS.md — `server/auth/` — identity and access

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Rules for accounts, sessions, invitations, roles, memberships, the optional functions and what
a subject lets its students use. The code is `server/auth/` (with its queries,
`queries.py`, the optional functions, `features.py`, and its routes, `router.py`) and the
invitations of `server/admin/invites.py`. The people of a subject, a teacher's links and the
groups of a class are `server/classroom/AGENTS.md`.

## Identity (`server/auth/`)

Own passwords, own server-side sessions, no OAuth/IdP/JWT.

- **No registration endpoint, ever.** Accounts come from single-use invitations or
  `create-user`. The person registering chooses their username and language, and nothing
  else: the account's profile is the invitation's.
- **The account's profile** (`users.evaluator_profile`, decided 2026-10-06): every account is
  a teacher or a student, and the INVITATION says which (`invites.profile`, required in the
  panel's form and in `system invite --profile`; a row with none is a student's). The
  registration form asks nothing and `/accept` ignores an `evaluator_profile` sent to it; the
  preview says `profile`. It only climbs: `POST /api/admin/accounts/{id}/profile` takes
  `teacher` and nothing else (409 `profile_only_climbs`), and `set_admin` makes an
  administrator a teacher. It decides ONE thing outside the subjects — a teacher creates them
  (`POST /api/workspaces`, 403 `cannot_create` otherwise; `can_create` on the listing), with
  no administrator bypass — and nothing inside one. A NULL left over reads as a student.
  Migration 0017 made every account without one, and every administrator, a teacher.
  `create-user` requires `--profile`. A membership records how it began (`via`: `owner`,
  `admin`, `invite`, `class_link`, `cli`; NULL before 0017) and who let it in
  (`invited_by`).
- Argon2id; policy is length plus rejecting the obvious. No HIBP.
- **Username enumeration is refused in three places at once** (`/login` uniform answer +
  decoy hash timing, `/forgot` always 202). Weakening one re-opens it.
- Sessions: opaque token, SHA-256 in DB, sliding 14 d + absolute 30 d, rotate on login and
  password change, password change revokes other sessions.
- **Authorisation is a membership row, checked on every route** (`auth.VIEW`/`EDIT`/`MANAGE`).
  The admin bypass exists only in `auth.deps.access_for`, which also gives an administrator
  the owner's role whatever its membership says, so `auth.at_least(access, level)` — for a
  route that lets part of what it does through only at a higher level — compares roles and
  nothing else. The WebSocket authenticates before `accept()` (close 4401) and filters
  events by workspace and, for a private job, by author. A refused membership carries
  `X-Error-Code`: `not_member` (no row for the workspace named) or `role_too_low`.
- **The three roles are a class** (decided 2026-10-06): `viewer` is a student of the subject,
  `editor` a teacher, `owner` the teacher who answers for it; `ROLE_RANK` stays linear. A
  student reads the syllabus (the `/api/kg` reads), the subject's description, its types
  of exercise and, since 2026-10-14, the bank as its teachers showed it (`GET /api/exercises`,
  `auth.VIEW`: the exercises shown to the class or to their group, each cut to the fields
  shown, with its type, level and concepts, never its origin, author or the tagger's trace;
  `bank/reading.reading`), and queues only `catalogue.STUDENT_KINDS` (`generate`, `evaluate`, and
  `tutor_turn` joined at the tutor's install), each behind its own permission. The bank
  (`/api/bank`, its coverage included), the raw documents and their transcriptions
  (`/api/raw`), the graph's document verbatim (`GET /api/kg/raw`) and a stage's history
  (`GET /api/pipeline/{artifact}/history`) are `auth.EDIT`, reads included. `POST /api/jobs`
  and `DELETE /api/jobs/{id}` are `auth.VIEW` and decide inside: any other kind is
  `role_too_low` for a student, a student's `force` is ignored (here and on
  `POST /api/evaluation`), and a student cancels their own jobs only. The evaluation's own
  routes are `auth.VIEW` + `auth.EVALUATION`, and a student deletes their own exercises.
  `tests/server/auth/test_route_roles.py` reads every mounted route and pins the level it
  declares against a table: a route with no row fails.
- CSRF is an origin check (`core/middleware.py`); CORS off by default. Rate limiting is in memory,
  keyed by IP and account. **A school's network counts the account alone** (decided
  2026-10-06): behind its NAT a class is one address and the ninth login was refused, so an
  address inside `access.trusted_networks` (`TRUSTED_NETWORKS`, env
  `VARIATIO_TRUSTED_NETWORKS`, edited in «Administración → Cuentas → Acceso») skips the IP
  key of every bucket (`rate_limit._keys`); the account or link key is always counted, and a
  bucket with no account (`reset`) keeps its IP. The list is read on every attempt, stores
  each network as its network address and refuses one wider than /8 (IPv4) or /32 (IPv6)
  (`registry/access.networks`, the setting's `clean`).
- **The administrator chooses who uses each function** ([features.py](features.py), `GATED`):
  generating, the evaluation, the tutor and the chat are each `off`, `all` or `selected` (a
  list of accounts), set in «Administración → Funciones» (`GET /api/admin/features`,
  `PUT /api/admin/features/{feature}`; the list is replaced only when `accounts` is sent and
  survives a change of mode). **The evaluation and the tutor are the optional functions**
  (`FEATURES`): with no row they are off, and an invitation may list its holder for them.
  Generating and the chat (D-233, 2026-10-19) are open to every account with no row, so an
  upgrading installation keeps them; the jobs route reads generating's mode, `auth.CHAT` the
  chat's.
  `auth.EVALUATION` and `auth.TUTOR` sit beside `auth.VIEW` on the routers of
  `/api/evaluation`, `/api/stage-evaluations` and `/api/tutor`, and `catalogue.FEATURE_OF`
  closes `POST /api/jobs` for an `evaluate` job. **No administrator bypass**: the admin lists
  their own account. The admin's read routes are not behind it. A refusal is a 403 with
  `X-Error-Code: feature_off`. `/api/auth/me` carries `features`. An invitation may list its
  holder (`invites.features`), applied at registration. `GET /api/health` leaves out the
  models only a switched-off function names. **The tutor may list whole subjects too**
  (the class plan's phase 15; migration 0020, `feature_subjects`): under `selected`,
  everybody in a listed subject uses it THERE, whoever joins later included, and not in their
  other subjects (`features.enabled(session, user, feature, workspace)`, `SUBJECT_LISTED` =
  the tutor, and since 2026-10-19 generating and the chat: the evaluation stays account by
  account, and `workspaces` for it is a 422). `PUT /api/admin/features/{feature}` takes
  `workspaces` (slugs; replaced only when sent, like `accounts`), the snapshot lists them, and
  «Permisos de uso» draws «Asignaturas elegidas» above «Cuentas elegidas», its state sentence
  naming the three things.
- **What a subject lets its students use** (decided 2026-10-06; migration 0019): switches
  of the subject, `workspaces.student_generate` and `student_tutor` (open by default) and,
  since 2026-10-15, `student_chat` (closed by default, migration 0023), that
  its teachers set in «Clase → Funcionalidades permitidas» (`GET`/`PATCH /api/members/uses`,
  `auth.EDIT`; the answer says `tutor_installed` and `tutor_offered`, whether the
  administrator opened the tutor to one of its students: the tutor's switch is drawn wherever
  the tutor is installed, and off and still, with the reason, until it is offered). They bind students alone.
  `features.refusal(session, user, feature, workspace, role)` is the one reading — the
  administrator's mode first, then a student's switch — used by `require_feature` (which
  reads the request's `Access` through `deps.require_viewer`, the callable `auth.VIEW` wraps,
  so the membership is resolved once), by `POST /api/jobs` (`generate` included) and by
  `features.for_user`, which `/api/auth/me` answers for the subject the account lands in:
  `features` carries `generate` beside the two functions. Generating is not an optional
  function (no tone, open with no row): the client reads it with `featuresOf` (only a
  literal `false` closes it), `usesFor` drops its door and `/generate` draws «not found»; a
  student's exercises stay in «Mis asignaturas y ejercicios».
- Invitations are the admin's alone (`admin/invites.py`): chosen expiry (floor, no ceiling),
  an internal alias never shown to the invitee, batches, link kept **sealed** with Fernet
  (key in `VARIATIO_INVITE_LINK_KEY` or `/.invite_link_key`, never in the DB), readable again
  via `GET /{id}/link`, and pastable back after deletion. The sealed copy dies with the use.
- Deleting an account: its generated exercises stay as files nobody reads any more;
  `evaluation_sessions` keep their rows (`SET NULL`); `stage_evaluations` cascade.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

**Identity and access**
- D-087, D-088, D-089 — Invitation-only sign-up (single-use invitations, class-link seats,
  `create-user`), own auth, no JWT, username identity, email optional. An account enters a
  subject with a link, never by its username.
- D-090 — The profile («Docente» / «Alumno») is the invitation's; only the administrator
  raises it, nothing lowers it; it decides one thing, creating subjects.
- D-092, D-093 — Membership checked on every route; admin bypass in one place.
- D-094 — The per-address limit skips the networks the administrator lists as a school's:
  from them only the account is counted.
- D-096, D-097 — A subject's teachers decide whether its students generate or use the tutor
  (after the administrator's mode); a group's switch, when set, wins.
- D-100, D-102 — `viewer` is «Alumno»: reads the syllabus, and the bank as its teachers show
  it; generates, evaluates or uses the tutor by permission; sees nothing else of the
  construction. No fourth role.
- D-104 — Links are sealed, never stored in clear. The class's links and people (D-105, D-107)
  are `classroom/AGENTS.md`'s.
- D-108, D-109, D-110 — No «forgot password» on the login screen; no password generator; no
  session list.
- D-123, D-124, D-125 — The evaluation and the tutor are switched by the administrator for
  nobody, everybody or a list of accounts (the tutor also of subjects); both start off; no
  exemption for the administrator; the tutor's daily limit is the account's.
- D-233 — Generating and the chat are switched the same way (also by subjects), and start
  open to every account.
