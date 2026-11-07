# AGENTS.md — `server/workspaces/` — the subjects of an account

Read the root `AGENTS.md` and `server/AGENTS.md` first.

`router.py` is `/api/workspaces`: the selector's list, creating a subject, entering one,
leaving it and deleting it. `trees.py` is a subject's tree on disk. Resolving a slug to its
paths is `core/installation.py`, and a request's subject is resolved once, by
`auth.require_member`.

- **Creating a subject is every teacher's**: the account's profile
  (`users.evaluator_profile`), which its invitation set. A student creates none, and there is
  no administrator bypass here.
- **A deletion that leaves no other member takes the tree too; if others remain, the files
  stay**, their notes and the generated exercises with them. `remove` and `leave` obey that
  one condition and report it as `files_removed`. The roster is read before the cascade takes
  the rows, and the tree goes before the row, so a failure leaves a row to retry rather than
  an orphan tree. The administration panel deletes any subject
  (`DELETE /api/admin/workspaces/{slug}`) under the same rule.
- `trees.destroy` and `trees.clear_cache` refuse any path that is not a direct child of
  `WORKSPACES_DIR` (`_contained_root`). Emptying the cache keeps the concept descriptions and
  the corpus anchoring, which cost a long model run.

## Rules

One line per rule of this folder. A number names an entry of the old register:
`git show 6698e16:DECISIONS.md`.

- D-115 — A deletion that leaves no other member takes the subject's tree; if others remain,
  the files stay; the tree goes before the row.
