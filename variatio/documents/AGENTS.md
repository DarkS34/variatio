# AGENTS.md — `variatio/documents/` — reading documents and transcription

Read the root `AGENTS.md` first. The closed decisions are numbered in the root `DECISIONS.md`.
Rules for reading a raw document and transcribing it page by page. `pages/` is a package by
step (`document`, `cache`, `render`, `transcribe`, `office_pages`, `images`, `seams`; its
`__init__.py` is the map) and re-exports every name; a test patches a name in the module that
LOOKS IT UP, which for `page_images`, `page_count` and `_transcribe_page` is `pages.document`.
The server's side is `server/raw/documents.py` and `server/raw/originals.py`
(`server/raw/AGENTS.md`); the reader is `web/src/features/raw/AGENTS.md`.

## Transcription (`server/raw/documents.py`, `entrypoints/transcribe.py`)

**An accelerator, never a gate**: every builder keeps its own conversion phase; `transcribe`
has no `GATES`/`NEEDS_APPROVED` entry, nothing chains after it, and it writes no artifact.
What it decides is step 1's state in the bar: done only once every document is read
(2026-10-12, *Navigation and the three steps* in `web/AGENTS.md`); no build waits for it.
Both raw slots use the same VLM page route (quality over speed).

- Per document state `done`/`pending`/`stale` **with the reason** (model, DPI, OCR, deck,
  cleanup…). Hand-edited pages win over the model and survive every build; editing drops only
  the two seam records around the page. The last page cannot be deleted.
- Page seams: deterministic first, the `transcribe_seam` model only classifies ambiguous ones
  and never rewrites; fails open. Seam decisions are cached in `_meta.json`.
  `<!-- page N -->` marks only paragraph seams.
- **A document is its bytes**: the same PDF anywhere in the installation arrives read
  (`pages.reuse_key`, `adopt_pages` copies — never links — pages from a donor with an
  identical fingerprint minus `source`), at upload and at the head of `transcribe_slot`.
- **All PDFium calls go through `pages.render._PDFIUM_LOCK`** (process-wide RLock, released between
  pages, documents closed under the lock). PDFium is not thread-safe and one corruption
  poisons the process.
- Scanned pages (no text layer) go as JPEG (`TRANSCRIBE_PAGE_JPEG_QUALITY`); renders are capped
  at `TRANSCRIBE_PAGE_MAX_A4_AREAS`; these, the picture sizes and the metafile scale are in
  the fingerprint, a meta lacking them reading as `pages.RENDER_BEFORE` (the values they had
  as constants), and top-k/top-p enter it only when set; MIME is
  read off the bytes. A failed page of a finished PDF is re-read on its own later, unless
  pages were inserted/deleted by hand (`restructured`) or the page count changed.
- **Truncation and loops**: `TRANSCRIBE_MAX_OUTPUT_TOKENS` (4096) caps each answer;
  `inference.generate(stop_on_loop=True)` cuts a repetition loop in the stream
  (`core/repetition.py`). An unfinished answer is retried ONCE with a note naming the loop;
  if still unfinished the page keeps the text before the loop under the failed-page marker
  (pictures are not salvaged). Cached pages are scanned for loops and re-read. There is **no
  prompt version**: a prompt change re-reads nothing (`RETIRED_FIELDS` drops old fingerprint keys).
- Office files: Docling translates the text; EMF/WMF are rasterised through LibreOffice on a
  copy first (`documents/office.py`, PNG filter, two passes at 4×, cropped); each body picture
  is **transcribed** (never merely described) with the page model under `IMAGE_RULES`, cached
  by content hash workspace-wide (failures never cached; `EMPTY_IMAGE_MARK` cached and leaves
  nothing). Header/furniture pictures are never read.
- **A deck is one page per slide**, each with its speaker notes quoted below as a blockquote
  (`wording.speaker_notes_block`), read with python-pptx, no model call; seams between slides
  are fixed paragraphs.
- **Diagrams are transcribed as Mermaid** (`IMAGE_RULES`: labelled nodes and edges → a fenced
  mermaid block of the fitting type; surrounding text outside the block; big or illegible
  trees → `[figura: …]`).
- Docling's own escapes are undone on its output only (`markdown.undo_converter_escapes`),
  outside fences; never on a transcribed page or a hand-written `.md`.

## Closed decisions

One line per rule in force; the date, commit and reason of each are in
the root `DECISIONS.md`. Do not reverse one without the user's explicit request.

- D-025, D-026, D-028…D-031 — Transcription is an accelerator and a step of `/raw`, never a
  gate or a stage; step 1 reads done only with every document read; both slots use the VLM
  page route; no PDF→DOCX; Office pictures read with the page model; metafiles rasterised
  through LibreOffice PNG export on a copy.
- D-032 — A build waits for a live transcription of its slot (concurrency, not a gate).
- D-082, D-084 — A transcription answer at the output cap or in a loop is a failed page (after
  one noted retry, salvaged up to the loop); there is no prompt version.
