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
from ..core import inference, progress
from ..core.json_io import write_json
from ..core.repair import parse_with_repair
from ..instance.content_context import ContentContext
from ..instance.knowledge_graph import KnowledgeGraph
from .vectors import embed_normalized

# Grammar-constrained decoding, and not a bare `think=False`. `DESCRIPTION_GENERATION_LLM`
# is a reasoning model, and with the reasoning channel closed it reasons INSIDE the answer:
# on the reference instance, the description of «Error de compilación» is 9 000 characters
# of English deliberation — «The user is asking for…», «Let's re-read the relations
# carefully» — stored as is and indexed as if it were prose. Under the grammar the first
# token already has to be `{`, so that failure has nowhere to go.
DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {"description": {"type": "string"}},
    "required": ["description"],
}


# The batch answer's keys are pinned to the exact concept names and every one is required,
# which is the same move `tagging_schema` makes with its `enum`: the prompt already demands
# «una entrada por cada concepto, ni una más ni una menos», and this is that rule stated
# where the decoder enforces it instead of hoping. Without it a batch that silently drops
# three concepts looks like a successful call.
def _batch_schema(concepts: list[str]) -> dict:
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
    try:
        data = json.loads(response)
    except json.JSONDecodeError as e:
        return None, str(e)
    if not isinstance(data, dict):
        return None, "la respuesta no es un objeto"
    written = data.get("descriptions")
    if not isinstance(written, dict):
        return None, "falta el objeto «descriptions»"

    out = {}
    for concept in concepts:
        text = written.get(concept)
        if not isinstance(text, str) or not text.strip():
            return None, f"falta la descripción de «{concept}»"
        out[concept] = " ".join(text.split())
    return out, None


# The descriptions file is a `{concepto: texto}` cache and nothing else: reading or writing
# it needs neither the graph nor the exemplars profile. These live outside `ConceptDescriber`
# because demanding the whole describer to touch the file coupled reading the GRAPH to an
# artifact the graph does not depend on — which is exactly why the graph screen answered 404
# while the profile was missing. `review.UPSTREAM` states it: the graph has no upstreams.
def load_descriptions(path: str | Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_descriptions(path: str | Path, descriptions: dict[str, str]) -> None:
    write_json(path, descriptions)


# The corpus anchoring the graph build writes: `{"documents": [...], "concepts":
# {concept: [{document, location, text}]}}`. It is read the way the descriptions are read
# — only the file — because a workspace whose graph arrived imported does not have it, and
# that is not an error: it is described from the relations, as before it existed.
def load_sources(path: str | Path) -> dict:
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
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        context: ContentContext,
        prompts,
        path: str | Path,
        sources_path: str | Path,
        siblings_top_k: int = config.DESCRIPTION_SIBLINGS_TOP_K,
        collision_similarity: float = config.DESCRIPTION_COLLISION_SIMILARITY,
    ):
        self.knowledge_graph = knowledge_graph
        self.context = context
        self.prompts = prompts
        self.path = Path(path)
        self.sources_path = Path(sources_path)
        self.siblings_top_k = siblings_top_k
        self.collision_similarity = collision_similarity
        self._name_vectors: dict[str, np.ndarray] | None = None

        sources = load_sources(self.sources_path)
        self.passages: dict[str, list[dict]] = sources["concepts"]
        # Naming the document only helps when there are several; with one it repeats the same
        # line in every passage of every concept and distinguishes nothing.
        self.name_documents = len(sources["documents"]) > 1

    def load(self) -> dict[str, str]:
        return load_descriptions(self.path)

    def save(self, descriptions: dict[str, str]) -> None:
        save_descriptions(self.path, descriptions)

    # FRESHNESS -------------------------------------------------------------------------------

    # A description is written from a concept's domain and relations, so it goes stale when
    # those change — and nothing noticed: a graph rebuilt twice kept describing `Caso base`
    # with the text of `Recursividad`, from a graph two versions old, because the concept
    # name still existed and the cache is keyed by name alone. The fingerprints live in a
    # sidecar so the descriptions file stays the plain {concept: text} map the editors read.
    # A concept with no recorded fingerprint adopts the current one instead of regenerating:
    # a cache written before this existed is not evidence of staleness.
    @property
    def fingerprints_path(self) -> Path:
        return self.path.with_suffix(".fingerprints.json")

    def _fingerprint(self, concept: str) -> str:
        payload = {
            "prompt": config.DESCRIPTION_PROMPT_VERSION,
            "domain": self.knowledge_graph.concept_domain[concept],
            "relations": {v: sorted(ns) for v, ns in self.collect_relations(concept).items()},
            # The anchoring enters the fingerprint because it enters the prompt: rebuilding the graph
            # over another corpus changes what the concept means here, and a description written
            # against the previous paragraphs no longer describes the same thing.
            "passages": [p.get("text", "") for p in self.passages.get(concept, [])],
            # The context enters too, and that was a gap: the prompt reads it to fix the subject, the
            # level and the language, so changing subject changes what a description should say.
            # Without this, editing the context left descriptions written against the previous one
            # intact. It is cheaper than it looks: the context is one for the whole instance, so
            # either nothing changes or all of them are rewritten, which is exactly right in that
            # case.
            "context": self.context.prompt_block(),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(blob.encode("utf-8")).hexdigest()[:12]

    def _load_fingerprints(self) -> dict[str, str]:
        if not self.fingerprints_path.exists():
            return {}
        try:
            with self.fingerprints_path.open(encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    # Merged, never replaced: `ensure(concepts=[...])` describes a subset, and writing only
    # that subset's fingerprints would mark every other concept as never-seen.
    def _save_fingerprints(self, fingerprints: dict[str, str]) -> None:
        merged = {**self._load_fingerprints(), **fingerprints}
        write_json(self.fingerprints_path, merged, sort_keys=True)

    def restamp(self, dry_run: bool = False) -> tuple[int, int]:
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
        stored = self._load_fingerprints()
        missing = [c for c in targets if c not in descriptions]
        stale = [
            c for c in targets if c in descriptions and c in stored and stored[c] != current[c]
        ]
        if stale:
            logger.info(
                f"{len(stale)} descripción(es) quedaron obsoletas al cambiar el grafo; "
                "se reescriben"
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
        descriptions = self.load() if descriptions is None else dict(descriptions)
        targets = concepts if concepts is not None else self.knowledge_graph.taggable_concepts

        current = {c: self._fingerprint(c) for c in targets}
        pending = list(targets) if overwrite else self._pending(targets, descriptions, current)
        if pending:
            logger.info(f"Escribiendo {len(pending)} descripción(es) de concepto")
            self._write(self._by_domain(pending), descriptions)
        else:
            logger.info(f"{len(targets)} descripción(es) de concepto reutilizadas de la caché")

        # The second pass is NOT run over everything that has siblings. It was, and it
        # doubled the calls to fix a problem most concepts do not have — while the ones that
        # do have it were being produced by the FIRST pass, which showed a whole domain at
        # once and got imitation instead of contrast (three pairs came back byte-identical).
        # So: contrast against a handful of near names on the way in, then measure what
        # actually collided and rewrite only that, against the concept it collided with.
        #
        # It runs even when nothing was pending, because that is precisely the state a
        # damaged cache sits in — all present, two of them identical, and no reason to look.
        # The check itself is one batch of embeddings; only a real collision costs a call.
        written = len(pending)
        if refine:
            collisions = self._collisions(descriptions, list(targets))
            if collisions:
                logger.info(f"Reescribiendo {len(collisions)} descripción(es) que chocan con otra")
                self._write(list(collisions), descriptions, against=collisions)
                written += len(collisions)

        self._save_fingerprints(current)
        if written:
            logger.success(f"{written} descripción(es) escritas; {len(descriptions)} en la caché")
        return descriptions

    def _write(
        self,
        plan: list[str],
        descriptions: dict[str, str],
        against: dict[str, list[str]] | None = None,
    ) -> None:
        # `against` is the refine pass rewriting one description against the one it collided
        # with, which is a per-concept question and stays per-concept. Everything else goes out
        # one domain at a time.
        if against is not None:
            self._write_one_by_one(plan, descriptions, against)
            return

        groups: dict[str, list[str]] = {}
        for concept in plan:
            groups.setdefault(self.knowledge_graph.concept_domain[concept], []).append(concept)

        with progress.step(
            "descriptions", "Generando descripciones de conceptos", total=len(plan)
        ) as reporter:
            done = 0
            for domain, batch in groups.items():
                progress.checkpoint()
                reporter.tick(done + 1, detail=f"{domain} ({len(batch)})")
                try:
                    descriptions.update(self.describe_domain(domain, batch, descriptions))
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.warning(f"[{domain}] el lote falló, se escribe uno a uno: {e}")
                    self._write_one_by_one(batch, descriptions, {})
                done += len(batch)
                reporter.tick(done, detail=domain)
                # Checkpoint after every domain: a cancelled run keeps what it wrote.
                self.save(descriptions)

    def _write_one_by_one(
        self, plan: list[str], descriptions: dict[str, str], against: dict[str, list[str]]
    ) -> None:
        for concept in plan:
            progress.checkpoint()
            try:
                descriptions[concept] = self.describe(
                    concept, descriptions, against=against.get(concept)
                )
            except progress.Cancelled:
                raise
            except Exception as e:
                logger.warning(f"[{concept}] descripción de reserva, sin modelo: {e}")
                descriptions[concept] = self.simple_describe(concept)
            self.save(descriptions)

    def _by_domain(self, concepts: list[str]) -> list[str]:
        return sorted(concepts, key=lambda c: (self.knowledge_graph.concept_domain[c], c))

    def describe(
        self,
        concept: str,
        descriptions: dict[str, str] | None = None,
        against: list[str] | None = None,
    ) -> str:
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
            raise ValueError(f"descripción ilegible: {error}")
        return parsed

    def simple_describe(self, concept: str) -> str:
        """The offline fallback. It delegates to `collect_relations` so the two can never
        disagree about which relations feed a description."""
        domain = self.knowledge_graph.concept_domain[concept]
        lines = [f'Concepto: "{concept}".', f'Dominio: "{domain}"']
        lines.extend(
            f'{verb}: {", ".join(neighbors)}.'
            for verb, neighbors in self.collect_relations(concept).items()
        )
        return "\n".join(lines)

    # CONTRAST --------------------------------------------------------------------------------

    # Contrast is only useful against the few concepts this one could be confused WITH.
    # Pasting the whole domain — up to 35 descriptions here — buries the instruction to
    # differentiate under a wall of prose to imitate, which is exactly what happened.
    def siblings(self, concept: str) -> list[str]:
        domain = self.knowledge_graph.concept_domain[concept]
        pool = [
            c
            for c in self.knowledge_graph.concepts_by_domains[domain]
            if c != concept and c not in self.knowledge_graph.generic_non_taggable_concepts
        ]
        if len(pool) <= self.siblings_top_k:
            return pool
        return self._nearest_names(concept, pool, self.siblings_top_k) or pool[: self.siblings_top_k]

    # The shortlist for contrast comes from the NAMES, which is cheap and needs nothing
    # written yet; whether two descriptions really collide is then measured on the
    # descriptions themselves, in `_collisions`, once they exist.
    def _nearest_names(self, concept: str, pool: list[str], k: int) -> list[str]:
        vectors = self._names()
        if vectors is None or concept not in vectors:
            return []
        anchor = vectors[concept]
        scored = [(float(anchor @ vectors[c]), c) for c in pool if c in vectors]
        scored.sort(reverse=True)
        return [c for _, c in scored[:k]]

    def _names(self) -> dict[str, np.ndarray] | None:
        if self._name_vectors is None:
            concepts = self.knowledge_graph.taggable_concepts
            matrix = embed_normalized(concepts, "concept names")
            self._name_vectors = {} if matrix is None else dict(zip(concepts, matrix))
        return self._name_vectors or None

    # Collisions are looked for across ALL concepts, not just within a domain: the pairs
    # that hurt retrieval are the ones the index cannot separate, and the domain partition
    # has no say in that (`Concatenación` and `operaciones con cadenas` landed in different
    # domains and still scored 0.896).
    def _collisions(self, descriptions: dict[str, str], targets: list[str]) -> dict[str, list[str]]:
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
                    f"[{concept}] choca con {', '.join(peers)} (máx {similarity[i].max():.3f})"
                )
        return collisions

    # BATCH -----------------------------------------------------------------------------------

    # One call per domain instead of one per concept. Writing them one at a time made
    # differentiation a REQUEST — the siblings block asks for it and the model answered by
    # copying the sibling and changing its first verb («Detectar y corregir…» against
    # «Identificar y corregir…», cosine 0.969). Written together it is a CONSTRAINT: the
    # competing descriptions are in the same answer, so separating them is the task and not
    # an afterthought.
    def describe_domain(
        self, domain: str, concepts: list[str], written: dict[str, str] | None = None
    ) -> dict[str, str]:
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
        lines = []
        for concept in concepts:
            lines.append(f"- {concept}")
            for verbose, neighbors in self.collect_relations(concept).items():
                lines.append(f"    · {verbose}: {', '.join(neighbors)}")
        return "\n".join(lines)

    # Each distinct passage once, with the concepts it yielded. A core passage feeds up to
    # eight of them, so per-concept repetition would spend the window on the same paragraphs
    # over and over — and, worse, would hide the very fact the model has to act on: that these
    # concepts came out of the SAME text and are therefore the ones at risk of collapsing
    # into one another.
    def _batch_passages_block(self, concepts: list[str]) -> str:
        wanted = set(concepts)
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
                place = entry.get("location") or ""
                if self.name_documents:
                    place = " · ".join(p for p in (entry.get("document") or "", place) if p)
                places.setdefault(text, place)

        blocks = []
        for text, owners in by_text.items():
            head = f"[{places[text]}]" if places[text] else ""
            named = ", ".join(o for o in owners if o in wanted)
            blocks.append(f"{head}\nCONCEPTOS EXTRAÍDOS DE AQUÍ: {named}\n\n{text}")
        return "\n\n---\n\n".join(blocks)

    # A partial batch still has to separate itself from the siblings it is NOT rewriting,
    # or an incremental top-up would land on top of a description nobody asked to change.
    def _existing_block(self, domain: str, batch: list[str], written: dict[str, str]) -> str:
        taggable = set(self.knowledge_graph.taggable_concepts)
        rest = [
            c
            for c in self.knowledge_graph.concepts_by_domains.get(domain, [])
            if c in taggable and c not in set(batch) and (written.get(c) or "").strip()
        ]
        return "\n".join(f"- {c}: {' '.join(written[c].split())}" for c in rest)

    def _domains_block(self, current: str) -> str:
        lines = []
        for domain, names in self.knowledge_graph.concepts_by_domains.items():
            mark = " (el que estás describiendo)" if domain == current else ""
            lines.append(f"- {domain}{mark}: {', '.join(names)}")
        return "\n".join(lines)

    # RELATIONS -------------------------------------------------------------------------------

    # Only relations flagged `use_in_embedding` feed a description.
    def collect_relations(self, concept: str) -> dict[str, list[str]]:
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
