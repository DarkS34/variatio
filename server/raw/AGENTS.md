# AGENTS.md — `server/raw/` — step 1, «Apuntes y ejercicios»

Read the root `AGENTS.md` and `server/AGENTS.md` first. The closed decisions are numbered in
the root `DECISIONS.md`. The transcription itself is `variatio/documents/AGENTS.md`, and the
screen `web/src/features/raw/AGENTS.md`.

`router.py` is `/api/raw`: the two slots, uploading and deleting a document, and the
transcription and its pages. `documents.py` lists and writes the slots' documents and reads
and corrects their pages; `originals.py` draws a document's original pages once and keeps
them. What each slot feeds, and the job that transcribes it, are the chain's
(`pipeline/slots.py`), because a build waits for a live transcription of the slot it reads.

- Routes under `/api/raw/{kind}/transcription…` are declared ABOVE `/{kind}/{name}`. Names
  from requests are checked against the slot's actual files.
