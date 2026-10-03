"""The notes cut into passages and embedded, so a question finds the paragraph it is about.

The graph already anchors each concept to up to three passages, and that covers a question
about a concept. It does not cover a question about a detail that is no concept, a concept
the build could not anchor, or a message no concept matches — and the method demands a
reference to the notes in every reply. This index is that second road: the whole corpus, cut
by its own headings, searched by cosine with the vector the turn already computed.

It reads the TRANSCRIPTION the builders left in the page cache and never calls a model to
read a document: a document without finished pages is skipped and said once, since
transcribing is the raw-material screen's job and never a tutor turn's. Each passage keeps
its heading path and the syllabus unit it falls under, which is what lets a reply say
«Tema II, apartado de funciones» and lets the criteria builder read a unit's notes.

The index is regenerable and lives under `cache/embeddings/`, keyed by a fingerprint of the
embedding model, its prefix, the cut and the text, so a corrected page or a new cut rebuilds
it on the next turn and nothing else does.
"""

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger

from variatio import config as pipeline_config
from variatio.builders import source_docs
from variatio.builders.knowledge_graph_builder.extraction import is_navigation
from variatio.builders.source_docs.chunking import split_sections
from variatio.core import progress
from variatio.core.lexicon import fold
from variatio.core.workspace import Workspace
from variatio.runtime.embedder.vectors import embed_normalized, prefix_for

from . import paths

_FORMAT = 1

# A paragraph that is one markdown heading and nothing else.
_HEADING = re.compile(r"\A#{1,6} [^\n]*\Z")


@dataclass(frozen=True)
class Passage:
    """One piece of the notes: where it is, which unit it belongs to, and what it says."""

    id: str
    document: str
    location: str
    unit: str | None
    text: str

    def place(self) -> dict:
        """Return the reference a reply shows for it: the document and the heading path."""
        return {"document": self.document, "location": self.location, "unit": self.unit}


class PassageIndex:
    """The passages of one workspace's notes and their unit vectors, row for row."""

    def __init__(self, passages: list[Passage], matrix: np.ndarray, fingerprint: str):
        """Hold the passages and their matrix; an empty matrix is an index that finds nothing."""
        self.passages = passages
        self.matrix = matrix
        self.fingerprint = fingerprint
        self._by_id = {passage.id: passage for passage in passages}

    def __len__(self) -> int:
        """Return how many passages the index holds."""
        return len(self.passages)

    def search(
        self, vector: np.ndarray, k: int, threshold: float, exclude: set[str] | None = None
    ) -> list[tuple[Passage, float]]:
        """Return up to `k` passages at or above `threshold`, best first, skipping `exclude`."""
        if k <= 0 or not len(self.passages) or self.matrix.size == 0:
            return []
        scores = self.matrix @ vector
        found: list[tuple[Passage, float]] = []
        for row in np.argsort(-scores):
            score = float(scores[row])
            if score < threshold:
                break
            passage = self.passages[int(row)]
            if exclude and text_key(passage.text) in exclude:
                continue
            found.append((passage, score))
            if len(found) >= k:
                break
        return found

    def of_unit(self, unit: str) -> list[Passage]:
        """Return the passages that fall under one unit of the syllabus, in reading order."""
        return [passage for passage in self.passages if passage.unit == unit]

    def get(self, passage_id: str) -> Passage | None:
        """Return one passage by its id, or None."""
        return self._by_id.get(passage_id)


_indices: dict[str, PassageIndex] = {}
_lock = threading.Lock()


def index_for(ws: Workspace, sources: dict, max_chars: int) -> PassageIndex:
    """Return the workspace's passage index, building or reloading it only when it changed.

    Held per workspace slug for the life of the process and compared by fingerprint on every
    call, because the pages change under a live workspace — a corrected page, a document
    added — and a turn must then search the notes as they are. The lock serialises two turns
    of one workspace arriving together on the remote lane: both would embed the whole corpus.
    """
    passages = cut_corpus(ws, sources, max_chars)
    fingerprint = _fingerprint(passages, max_chars)
    with _lock:
        cached = _indices.get(ws.slug)
        if cached is not None and cached.fingerprint == fingerprint:
            return cached
        index = _load(paths.passages_cache_path(ws), passages, fingerprint)
        if index is None:
            index = _build(passages, fingerprint)
            if len(index):
                _save(paths.passages_cache_path(ws), index)
        _indices[ws.slug] = index
        return index


def forget(slug: str) -> None:
    """Drop one workspace's index from memory, so the next turn reads it again from disk."""
    with _lock:
        _indices.pop(slug, None)


def cut_corpus(ws: Workspace, sources: dict, max_chars: int) -> list[Passage]:
    """Cut every transcribed document of the corpus into passages, without calling a model.

    The documents are the ones the graph was built from (`concept_sources.json`), in its
    order; a workspace whose anchoring names none falls back to every document with pages.
    Cut by SECTION and never packed across sections, as the builders' chunker packs them for
    a model call: a passage is a reference, and one spanning two units has no place to
    name. A section longer than the cut is split by paragraphs. Navigation — a table of
    contents — is dropped, as the anchoring drops it, and so is a piece holding nothing but
    headings: it names a place and says nothing a reply could use.
    """
    units = [unit for unit in sources.get("units") or [] if isinstance(unit, dict)]
    passages: list[Passage] = []
    for name in _documents(ws, sources):
        text = _document_text(paths.corpus_pages_dir(ws) / name)
        if not text:
            continue
        unit: str | None = None
        for location, title, body in split_sections(text):
            unit = _unit_of(location, [title], units) or unit
            pieces = [body] if len(body) <= max_chars else source_docs.chunk_text(body, max_chars)
            for piece in pieces:
                kept = [
                    paragraph.strip()
                    for paragraph in re.split(r"\n\s*\n", piece)
                    if paragraph.strip() and not is_navigation(paragraph)
                ]
                if all(_HEADING.match(paragraph) for paragraph in kept):
                    continue
                passages.append(
                    Passage(
                        id=f"P{len(passages) + 1}",
                        document=name,
                        location=location,
                        unit=unit,
                        text="\n\n".join(kept),
                    )
                )
    return passages


def _documents(ws: Workspace, sources: dict) -> list[str]:
    """Return the corpus documents to read, the graph's own first."""
    named = [str(name) for name in sources.get("documents") or [] if name]
    if named:
        return named
    root = paths.corpus_pages_dir(ws)
    if not root.is_dir():
        return []
    return sorted(entry.name for entry in root.iterdir() if entry.is_dir())


def _document_text(directory: Path) -> str:
    """Return one document's transcription stitched as its build stitched it, or nothing."""
    pages = source_docs.read_pages(directory)
    if not pages:
        logger.warning(
            f"[tutor] «{directory.name}» no tiene páginas transcritas; el tutor no busca en él"
        )
        return ""
    seams = source_docs.valid_seams(source_docs.read_meta(directory).get("seams"))
    return source_docs.join_pages(pages, seams)


def _unit_of(location: str, headings: list[str], units: list[dict]) -> str | None:
    """Return the unit whose opening heading this chunk's path or headings carry, if any.

    The last match wins, because a chunk can start in one unit and open the next.
    """
    found = None
    names = [fold(part) for part in location.split(" > ") if part] + [fold(h) for h in headings]
    for unit in units:
        heading = fold(str(unit.get("heading") or ""))
        if heading and heading in names:
            found = str(unit.get("name") or "") or None
    return found


def text_key(text: str) -> str:
    """Return the key two copies of one passage share, to keep a card from quoting it twice."""
    return fold(text)[:200]


def _fingerprint(passages: list[Passage], max_chars: int) -> str:
    """Return what the index depends on: the embedding model, its prefix, the cut and the text."""
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {
                "format": _FORMAT,
                "model": pipeline_config.EMBEDDING_LLM,
                "prefix": prefix_for("document"),
                "chars": max_chars,
                "passages": [[p.document, p.location, p.unit, p.text] for p in passages],
            },
            ensure_ascii=False,
        ).encode("utf-8")
    )
    return digest.hexdigest()


def _build(passages: list[Passage], fingerprint: str) -> PassageIndex:
    """Embed every passage on the document side; an engine that cannot answer leaves it empty."""
    if not passages:
        return PassageIndex([], np.zeros((0, 0), dtype=np.float32), fingerprint)
    logger.info(f"[tutor] Indexando {len(passages)} pasaje(s) de los apuntes")
    prefix = prefix_for("document")
    with progress.step("tutor_passages", "Indexando los apuntes", total=len(passages)):
        matrix = embed_normalized([prefix + p.text for p in passages], "the tutor's notes")
    if matrix is None:
        return PassageIndex(passages, np.zeros((0, 0), dtype=np.float32), fingerprint + "-unembedded")
    return PassageIndex(passages, matrix, fingerprint)


def _load(path: Path, passages: list[Passage], fingerprint: str) -> PassageIndex | None:
    """Return the cached index when it was built from exactly these passages, else None."""
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            if str(data["fingerprint"]) != fingerprint:
                return None
            matrix = np.array(data["matrix"], dtype=np.float32)
    except (OSError, KeyError, ValueError) as exc:
        logger.warning(f"[tutor] El índice de los apuntes no se pudo leer ({exc}); se rehace")
        return None
    if matrix.shape[0] != len(passages):
        return None
    return PassageIndex(passages, matrix, fingerprint)


def _save(path: Path, index: PassageIndex) -> None:
    """Write the index atomically, so a cancelled turn never leaves half a cache behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez(temporary, matrix=index.matrix, fingerprint=np.array(index.fingerprint))
    os.replace(temporary, path)
