# AGENTS.md — `web/src/features/raw/` — step 1, «Apuntes y ejercicios»

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Read `web/AGENTS.md` and `web/DESIGN.md` first. The transcription's rules are in
`variatio/documents/AGENTS.md`.

## The document reader

- **A document opens as a reader of two columns** (`features/raw/DocumentReader.tsx`, user's
  decision of 2026-10-08; the tutor's reader moved here): «Original», the document as its
  author laid it out, beside «Texto», its transcription page by page, formatted. Every format
  takes one road (`server/originals.py`): a PDF as it is, an Office file exported to PDF by
  LibreOffice once (`office.pdf_copy`, a deck with its hidden slides), a page drawn by PDFium
  (`pages.page_picture`, under `_PDFIUM_LOCK`) as PNG, or JPEG when heavy; both kept under
  `cache/originals/` by the SOURCE's hash (the tutor's `cache/tutor_originals/` is adopted
  once per workspace). `GET /api/raw/{kind}/transcription/{name}` adds `original` (`pages`,
  `version`, `ratios` — each page's height over its width, so the reader lays the document
  out before a page arrives — `paired` and `unpaired`), and
  `GET …/transcription/{name}/original/{page}` serves one page as an image, cacheable because
  the client sends the version. **The columns go page to page where the cache holds one file
  per page of that very file** (same hash, not `restructured`, equal counts: a PDF, a deck);
  otherwise `unpaired` says why (`moved`, `source`, `count` — a Word file is one cached page)
  and each column scrolls on its own. The page read is the one at 25 % of the column
  (`reader/sync.ts`); a jump's own scroll is never read as the reader's. The bar turns the
  transcription's pages (the original's when the transcription is one page) and, under
  `lg`, the column in sight, chosen by a tab. It opens to READ: a page is corrected from its
  pencil, in place, one at a time; inserting and deleting wait while one is open. No
  original (plain text, the raw file gone, no LibreOffice, no PDFium) answers `original:
  null` and the reader shows the text alone, never an error. A document LibreOffice refuses
  is not asked for again until a restart.

## The screen `/raw`

- `/raw`: one entry per document, in a flat table (2026-10-07) whose head counts the documents;
  each entry two lines — the name, which opens the reader, and its type and pages read (no size: user's request, 2026-10-08)
  (user's request, 2026-10-08: one thin line each read as no list at all); each origin as tall as what it
  holds, never stretched to the other (user's request, 2026-10-08); multi-select delete; a finished origin carries a
  filled coral tick and no tint on its card (user's request, 2026-10-05); once both origins hold something, «Continuar» stands to the right of the
  title as on a stage (`WayOn`) — coral when everything is read, an outline while the
  reading block under the header holds the coral.
