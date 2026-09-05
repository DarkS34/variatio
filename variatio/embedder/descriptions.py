"""The prose concepts are matched against, and the file that caches it.

These descriptions ARE the retrieval surface: `top_k_concepts` scores an item against
their embeddings, so a bad description silently poisons every tag derived from it. Kept
apart from the index so a host can generate and review them as a step of its own, before
anything is indexed against them.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from loguru import logger

from .. import config
from .. import wording as wording_sets
from ..core import inference, progress
from ..core.json_io import write_json
from ..core.repair import parse_with_repair
from ..instance.content_context import ContentContext
from ..instance.knowledge_graph import KnowledgeGraph
from .vectors import embed_normalized

# Grammar-constrained decoding, not a bare `think=False`: with the reasoning channel closed
# this model reasons INSIDE the answer, and thousands of characters of deliberation end up
# stored as a description and indexed as prose. Under the grammar the first token must be `{`.
DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {"description": {"type": "string"}},
    "required": ["description"],
}


def _batch_schema(concepts: list[str]) -> dict:
    """Build the grammar for one domain's batch: every concept a required key.

    The prompt already demands one entry per concept and no more; pinning the keys is that
    rule stated where the decoder enforces it, so a batch that drops three concepts cannot
    look like a successful call.
    """
    return {
        "type": "object",
        "properties": {
            "descriptions": {
                "type": "object",
                "properties": {c: {"type": "string"} for c in concepts},
                "required": list(concepts),
            }
        },
        "required": ["descriptions"],
    }


def _parse_batch(response: str, concepts: list[str]) -> tuple[dict[str, str] | None, str | None]:
    """Parse a domain batch, returning `(descriptions, None)` or `(None, reason)`."""
    try:
        data = json.loads(response)
    except json.JSONDecodeError as e:
        return None, str(e)
    if not isinstance(data, dict):
        return None, "the answer is not an object"
    written = data.get("descriptions")
    if not isinstance(written, dict):
        return None, "the «descriptions» object is missing"

    out = {}
    for concept in concepts:
        text = written.get(concept)
        if not isinstance(text, str) or not text.strip():
            return None, f"the description of «{concept}» is missing"
        out[concept] = " ".join(text.split())
    return out, None


def load_descriptions(path: str | Path) -> dict[str, str]:
    """Read the `{concept: text}` cache — the file alone, no graph and no profile.

    Outside `ConceptDescriber` on purpose: demanding the whole describer to touch the file
    coupled reading the GRAPH to an artifact the graph does not depend on, and
    `review.UPSTREAM` states that the graph has no upstreams.
    """
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_descriptions(path: str | Path, descriptions: dict[str, str]) -> None:
    """Write the `{concept: text}` cache."""
    write_json(path, descriptions)


def load_sources(path: str | Path) -> dict:
    """Read the corpus anchoring a graph build wrote, tolerating its absence.

    A workspace whose graph arrived imported has none, and that is not an error: such a
    concept is described from its relations, as before the anchoring existed.
    """
    path = Path(path)
    empty = {"documents": [], "concepts": {}}
    if not path.exists():
        return empty
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(data, dict):
        return empty
    return {
        **data,
        "documents": data.get("documents") or [],
        "concepts": data.get("concepts") or {},
    }


def _parse_description(response: str) -> tuple[str | None, str | None]:
    """Parse one description, returning `(text, None)` or `(None, reason)`."""
    try:
        data = json.loads(response)
    except json.JSONDecodeError as e:
        return None, str(e)
    if not isinstance(data, dict):
        return None, "expected an object with a 'description' key"
    text = " ".join(str(data.get("description") or "").split())
    if not text:
        return None, "'description' is empty"
    return text, None


class ConceptDescriber:
    """Writes, refreshes and contrasts the prose each concept is retrieved by."""

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        context: ContentContext,
        prompts,
        path: str | Path,
        sources_path: str | Path,
        siblings_top_k: int | None = None,
        collision_similarity: float | None = None,
    ):
        """Bind a graph and its corpus anchoring to the cache they are described into."""
        self.knowledge_graph = knowledge_graph
        self.context = context
        self.prompts = prompts
        self._wording = wording_sets.beside(self.prompts)
        self.path = Path(path)
        self.sources_path = Path(sources_path)
        self.siblings_top_k = (
            config.DESCRIPTION_SIBLINGS_TOP_K if siblings_top_k is None else siblings_top_k
        )
        self.collision_similarity = (
            config.DESCRIPTION_COLLISION_SIMILARITY
            if collision_similarity is None
            else collision_similarity
        )
        self._name_vectors: dict[str, np.ndarray] | None = None

        sources = load_sources(self.sources_path)
        self.passages: dict[str, list[dict]] = sources["concepts"]
        # Naming the document only helps when there are several; with one it repeats the same
        # line in every passage of every concept and distinguishes nothing.
        self.name_documents = len(sources["documents"]) > 1

    def load(self) -> dict[str, str]:
        """Read the descriptions cache."""
        return load_descriptions(self.path)

    def save(self, descriptions: dict[str, str]) -> None:
        """Write the descriptions cache."""
        save_descriptions(self.path, descriptions)

    # FRESHNESS -------------------------------------------------------------------------------

    @property
    def fingerprints_path(self) -> Path:
        """The sidecar recording what each description was written against.

        A sidecar, so the descriptions file stays the plain `{concept: text}` map the
        editors read.
        """
        return self.path.with_suffix(".fingerprints.json")

    def _fingerprint(self, concept: str) -> str:
        """Digest everything a description is written from, so a change makes it stale.

        The cache is keyed by concept NAME alone, so without this a rebuilt graph kept
        describing a concept with text written against a version two graphs old. The
        anchoring and the subject context are in here because both reach the prompt.
        """
        payload = {
            "prompt": config.DESCRIPTION_PROMPT_VERSION,
            "domain": self.knowledge_graph.concept_domain[concept],
            "relations": {v: sorted(ns) for v, ns in self.collect_relations(concept).items()},
            "passages": [p.get("text", "") for p in self.passages.get(concept, [])],
            "context": self.context.prompt_block(),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(blob.encode("utf-8")).hexdigest()[:12]

    def _load_fingerprints(self) -> dict[str, str]:
        """Read the sidecar; an absent or corrupt one means nothing is known to be stale."""
        if not self.fingerprints_path.exists():
            return {}
        try:
            with self.fingerprints_path.open(encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_fingerprints(self, fingerprints: dict[str, str]) -> None:
        """Merge into the sidecar, never replace it.

        `ensure(concepts=[…])` describes a subset, and writing only that subset's
        fingerprints would mark every other concept as never-seen.
        """
        merged = {**self._load_fingerprints(), **fingerprints}
        write_json(self.fingerprints_path, merged, sort_keys=True)

    def restamp(self, dry_run: bool = False) -> tuple[int, int]:
        """Stamp the written descriptions against the current graph without rewriting them.

        Returns `(how many were stale, how many are written)`.
        """
        descriptions = self.load()
        written = [c for c in self.knowledge_graph.taggable_concepts if descriptions.get(c)]
        current = {c: self._fingerprint(c) for c in written}
        stored = self._load_fingerprints()
        changed = sum(1 for c in written if stored.get(c) != current[c])
        if not dry_run:
            self._save_fingerprints(current)
        return changed, len(written)

    def _pending(
        self, targets: list[str], descriptions: dict[str, str], current: dict[str, str]
    ) -> list[str]:
        """Return what has to be written: the missing ones, then the stale ones.

        A concept with no recorded fingerprint counts as fresh — a cache written before the
        sidecar existed is not evidence of staleness — and adopts the current stamp.
        """
        stored = self._load_fingerprints()
        missing = [c for c in targets if c not in descriptions]
        stale = [
            c for c in targets if c in descriptions and c in stored and stored[c] != current[c]
        ]
        if stale:
            logger.info(
                f"{len(stale)} description(s) went stale when the graph changed; "
                "rewriting them"
            )
        return missing + stale

    # WRITING ---------------------------------------------------------------------------------

    def ensure(
        self,
        descriptions: dict[str, str] | None = None,
        concepts: list[str] | None = None,
        overwrite: bool = False,
        refine: bool = True,
    ) -> dict[str, str]:
        """Write whatever is missing or stale, then rewrite whatever collides.

        The refine pass runs even when nothing was pending, because that is precisely the
        state a damaged cache sits in — all present, two of them identical, and no reason
        to look. It costs one batch of embeddings; only a real collision costs a call.
        """
        descriptions = self.load() if descriptions is None else dict(descriptions)
        targets = concepts if concepts is not None else self.knowledge_graph.taggable_concepts

        current = {c: self._fingerprint(c) for c in targets}
        pending = list(targets) if overwrite else self._pending(targets, descriptions, current)
        if pending:
            logger.info(f"Writing {len(pending)} concept description(s)")
            self._write(self._by_domain(pending), descriptions)
        else:
            logger.info(f"{len(targets)} concept description(s) reused from the cache")

        written = len(pending)
        if refine:
            collisions = self._collisions(descriptions, list(targets))
            if collisions:
                logger.info(f"Rewriting {len(collisions)} description(s) that collide with another")
                self._write(list(collisions), descriptions, against=collisions)
                written += len(collisions)

        self._save_fingerprints(current)
        if written:
            logger.success(f"{written} description(s) written; {len(descriptions)} in the cache")
        return descriptions

    def _write(
        self,
        plan: list[str],
        descriptions: dict[str, str],
        against: dict[str, list[str]] | None = None,
    ) -> None:
        """Write a plan one domain at a time, falling back to one call per concept.

        `against` is the refine pass rewriting one description against the one it collided
        with, which is a per-concept question and stays per-concept.
        """
        if against is not None:
            self._write_one_by_one(plan, descriptions, against)
            return

        groups: dict[str, list[str]] = {}
        for concept in plan:
            groups.setdefault(self.knowledge_graph.concept_domain[concept], []).append(concept)

        with progress.step(
            "descriptions", "Writing concept descriptions", total=len(plan)
        ) as reporter:
            done = 0
            for domain, batch in groups.items():
                progress.checkpoint()
                reporter.start(done + 1, detail=f"{domain} ({len(batch)})")
                try:
                    descriptions.update(self.describe_domain(domain, batch, descriptions))
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.warning(f"[{domain}] the batch failed, writing one by one: {e}")
                    self._write_one_by_one(batch, descriptions, {})
                done += len(batch)
                reporter.tick(done, detail=domain)
                # Checkpoint after every domain: a cancelled run keeps what it wrote.
                self.save(descriptions)

    def _write_one_by_one(
        self, plan: list[str], descriptions: dict[str, str], against: dict[str, list[str]]
    ) -> None:
        """Describe concepts one call at a time, falling back offline when the model fails."""
        for concept in plan:
            progress.checkpoint()
            try:
                descriptions[concept] = self.describe(
                    concept, descriptions, against=against.get(concept)
                )
            except progress.Cancelled:
                raise
            except Exception as e:
                logger.warning(f"[{concept}] fallback description, no model: {e}")
                descriptions[concept] = self.simple_describe(concept)
            self.save(descriptions)

    def _by_domain(self, concepts: list[str]) -> list[str]:
        """Order concepts by domain, so `_write` batches them in as few calls as it can."""
        return sorted(concepts, key=lambda c: (self.knowledge_graph.concept_domain[c], c))

    def describe(
        self,
        concept: str,
        descriptions: dict[str, str] | None = None,
        against: list[str] | None = None,
    ) -> str:
        """Write one concept's description, contrasted against its siblings."""
        domain = self.knowledge_graph.concept_domain[concept]
        relations = self.collect_relations(concept)
        written = descriptions or {}
        peers = self.siblings(concept) if against is None else against
        siblings = {c: written.get(c, "") for c in peers}

        prompt = self.prompts.concept_description_prompt(
            concept=concept,
            domain=domain,
            relations=relations,
            siblings=siblings,
            context_block=self.context.prompt_block(),
            passages=self.passages.get(concept),
            name_documents=self.name_documents,
        )
        response = inference.generate(
            model=config.DESCRIPTION_GENERATION_LLM,
            think=config.THINK_DESCRIPTION_GENERATION,
            prompt=prompt,
            format=None if config.THINK_DESCRIPTION_GENERATION else DESCRIPTION_SCHEMA,
            temperature=inference.judgement_temperature(config.THINK_DESCRIPTION_GENERATION),
        ).response
        parsed, error = parse_with_repair(
            response,
            _parse_description,
            config.REPAIR_LLM,
            config.MAX_JSON_REPAIR_TRIES,
            shape='{"description": "…"}',
            format=DESCRIPTION_SCHEMA,
            log_prefix=f"[{concept}] ",
            prompts=self.prompts,
        )
        if parsed is None:
            raise ValueError(f"unreadable description: {error}")
        return parsed

    def simple_describe(self, concept: str) -> str:
        """Compose a description offline, from the graph alone.

        It delegates to `collect_relations` so the two can never disagree about which
        relations feed a description.
        """
        domain = self.knowledge_graph.concept_domain[concept]
        lines = [f'Concepto: "{concept}".', f'Dominio: "{domain}"']
        lines.extend(
            f'{verb}: {", ".join(neighbors)}.'
            for verb, neighbors in self.collect_relations(concept).items()
        )
        return "\n".join(lines)

    # CONTRAST --------------------------------------------------------------------------------

    def siblings(self, concept: str) -> list[str]:
        """Return the few concepts this one could be confused with.

        Pasting the whole domain buries the instruction to differentiate under a wall of
        prose to imitate, which is what the shortlist exists to avoid.
        """
        domain = self.knowledge_graph.concept_domain[concept]
        pool = [
            c
            for c in self.knowledge_graph.concepts_by_domains[domain]
            if c != concept and c not in self.knowledge_graph.generic_non_taggable_concepts
        ]
        if len(pool) <= self.siblings_top_k:
            return pool
        return self._nearest_names(concept, pool, self.siblings_top_k) or pool[: self.siblings_top_k]

    def _nearest_names(self, concept: str, pool: list[str], k: int) -> list[str]:
        """Shortlist the k nearest concepts by NAME — cheap, and needs nothing written yet.

        Whether two descriptions really collide is measured on the descriptions themselves,
        in `_collisions`, once they exist.
        """
        vectors = self._names()
        if vectors is None or concept not in vectors:
            return []
        anchor = vectors[concept]
        scored = [(float(anchor @ vectors[c]), c) for c in pool if c in vectors]
        scored.sort(reverse=True)
        return [c for _, c in scored[:k]]

    def _names(self) -> dict[str, np.ndarray] | None:
        """Embed every taggable concept NAME once, or None when the engine cannot answer."""
        if self._name_vectors is None:
            concepts = self.knowledge_graph.taggable_concepts
            matrix = embed_normalized(concepts, "concept names")
            self._name_vectors = {} if matrix is None else dict(zip(concepts, matrix))
        return self._name_vectors or None

    def _collisions(self, descriptions: dict[str, str], targets: list[str]) -> dict[str, list[str]]:
        """Return each description that sits too close to another, with the ones it hits.

        Looked for across ALL concepts and not within a domain: the pairs that hurt
        retrieval are the ones the index cannot separate, and the domain partition has no
        say in that.
        """
        written = [c for c in targets if descriptions.get(c)]
        if len(written) < 2:
            return {}
        matrix = embed_normalized([descriptions[c] for c in written], "descriptions")
        if matrix is None:
            return {}

        similarity = matrix @ matrix.T
        np.fill_diagonal(similarity, 0.0)
        collisions: dict[str, list[str]] = {}
        for i, concept in enumerate(written):
            peers = [
                written[j]
                for j in np.argsort(-similarity[i])
                if similarity[i, j] >= self.collision_similarity
            ]
            if peers:
                collisions[concept] = peers
                logger.debug(
                    f"[{concept}] collides with {', '.join(peers)} (max {similarity[i].max():.3f})"
                )
        return collisions

    # BATCH -----------------------------------------------------------------------------------

    def describe_domain(
        self, domain: str, concepts: list[str], written: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Describe a whole domain in one call, so differentiating is the task itself.

        Written one at a time, differentiation is only a REQUEST and the model answers by
        copying the sibling and changing its first verb. Written together the competing
        descriptions are in the same answer, so separating them is a constraint.
        """
        prompt = self.prompts.describe_domain_concepts_prompt(
            domain=domain,
            concepts_block=self._batch_concepts_block(concepts),
            passages_block=self._batch_passages_block(concepts),
            context_block=self.context.prompt_block(),
            domains_block=self._domains_block(domain),
            existing_block=self._existing_block(domain, concepts, written or {}),
        )
        response = inference.generate(
            model=config.DESCRIPTION_GENERATION_LLM,
            think=config.THINK_DESCRIPTION_GENERATION,
            prompt=prompt,
            format=None if config.THINK_DESCRIPTION_GENERATION else _batch_schema(concepts),
            temperature=inference.judgement_temperature(config.THINK_DESCRIPTION_GENERATION),
        ).response
        parsed, error = parse_with_repair(
            response,
            lambda text: _parse_batch(text, concepts),
            config.REPAIR_LLM,
            config.MAX_JSON_REPAIR_TRIES,
            shape='{"descriptions": {"<concepto>": "…"}}',
            format=_batch_schema(concepts),
            log_prefix=f"[{domain}] ",
            prompts=self.prompts,
        )
        if parsed is None:
            raise ValueError(f"descripciones ilegibles para «{domain}»: {error}")
        return parsed

    def _batch_concepts_block(self, concepts: list[str]) -> str:
        """Render the batch's concepts with their relations, one indented line each."""
        lines = []
        for concept in concepts:
            lines.append(f"- {concept}")
            for verbose, neighbors in self.collect_relations(concept).items():
                lines.append(f"    · {verbose}: {', '.join(neighbors)}")
        return "\n".join(lines)

    def _passage_place(self, entry: dict) -> str:
        """Return where one passage came from, naming its document only if there are several."""
        place = entry.get("location") or ""
        if self.name_documents:
            place = " · ".join(p for p in (entry.get("document") or "", place) if p)
        return place

    def _group_passages(
        self, concepts: list[str]
    ) -> tuple[dict[str, list[str]], dict[str, str]]:
        """Group each distinct passage with the concepts it yielded, and where it is from."""
        by_text: dict[str, list[str]] = {}
        places: dict[str, str] = {}
        for concept in concepts:
            for entry in self.passages.get(concept) or []:
                text = (entry.get("text") or "").strip()
                if not text:
                    continue
                by_text.setdefault(text, [])
                if concept not in by_text[text]:
                    by_text[text].append(concept)
                places.setdefault(text, self._passage_place(entry))
        return by_text, places

    def _batch_passages_block(self, concepts: list[str]) -> str:
        """Render each distinct passage once, naming the concepts it yielded.

        A core passage feeds up to eight of them, so per-concept repetition would spend the
        window on the same paragraphs and — worse — hide the fact the model has to act on:
        that these concepts came out of the SAME text and are the ones at risk of
        collapsing into one another.
        """
        wanted = set(concepts)
        by_text, places = self._group_passages(concepts)

        blocks = []
        for text, owners in by_text.items():
            head = f"[{places[text]}]" if places[text] else ""
            named = ", ".join(o for o in owners if o in wanted)
            heading = self._wording.PASSAGE_CONCEPTS_HEADING
            blocks.append(f"{head}\n{heading}{named}\n\n{text}")
        return "\n\n---\n\n".join(blocks)

    def _existing_block(self, domain: str, batch: list[str], written: dict[str, str]) -> str:
        """Render the domain's descriptions the batch is NOT rewriting.

        A partial batch still has to separate itself from them, or an incremental top-up
        lands on top of a description nobody asked to change.
        """
        taggable = set(self.knowledge_graph.taggable_concepts)
        rest = [
            c
            for c in self.knowledge_graph.concepts_by_domains.get(domain, [])
            if c in taggable and c not in set(batch) and (written.get(c) or "").strip()
        ]
        return "\n".join(f"- {c}: {' '.join(written[c].split())}" for c in rest)

    def _domains_block(self, current: str) -> str:
        """Render every domain and its concepts, marking the one being described."""
        lines = []
        for domain, names in self.knowledge_graph.concepts_by_domains.items():
            mark = self._wording.DESCRIBING_MARK if domain == current else ""
            lines.append(f"- {domain}{mark}: {', '.join(names)}")
        return "\n".join(lines)

    # RELATIONS -------------------------------------------------------------------------------

    def collect_relations(self, concept: str) -> dict[str, list[str]]:
        """Return a concept's neighbours by relation, both directions named separately.

        Only relations flagged `use_in_embedding` feed a description.
        """
        kg = self.knowledge_graph
        relations: dict[str, list[str]] = {}

        for verb, graph in kg.graphs.items():
            if not kg.details(verb).get("use_in_embedding", True):
                continue
            if concept not in graph:
                continue
            if not graph.is_directed():
                neighbors = kg.neighbors(concept, verb)
                if neighbors:
                    relations[verb] = neighbors
                continue
            successors = kg.neighbors(concept, verb, direction="out")
            predecessors = kg.neighbors(concept, verb, direction="in")
            if successors:
                relations[f"este concepto {verb}"] = successors
            if predecessors:
                relations[f"{verb} este concepto"] = predecessors

        return relations
