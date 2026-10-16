# AGENTS.md — `server/kg/` — step 2, «Temario»

Read the root `AGENTS.md` and `server/AGENTS.md` first. The closed decisions are numbered in
the root `DECISIONS.md`. Building and reading the graph are the library's
(`variatio/AGENTS.md`); its chain and approval are `pipeline/AGENTS.md`.

`router.py` is `/api/kg`: the graph, its concepts, domains and relations, the document
verbatim, and the course's progress (`/api/kg/curriculum`, whose rules are in
`server/AGENTS.md`). `view.py` shapes the graph for the canvas; `edit.py` writes it.

- **Every write is validated** by loading the result through `KnowledgeGraph`, the class the
  pipeline uses, and only then replaces the file. A hand edit withdraws the graph's approval;
  the label review's own write seals it again (`kg_edit.set_non_taggable(…, reseal=True)`).
- A concept's or a domain's name is free text in the subject's language, so it travels in the
  body and never in the path.
- The router declares `auth.VIEW`, because a student reads the syllabus; every write adds
  `auth.EDIT`, and so does the document verbatim (`GET /api/kg/raw`), the construction's
  working copy.
