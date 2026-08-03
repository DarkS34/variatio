import hashlib
import json
from pathlib import Path

import numpy as np
from loguru import logger

from . import config, inference, progress
from .knowledge_graph import KnowledgeGraph
from .prompts import concept_description_prompt


class ConceptDescriber:
    """Writes and caches the prose that concepts are matched against.

    These descriptions *are* the retrieval surface: `top_k_concepts` scores an item
    against their embeddings, so a bad description silently poisons every tag derived
    from it. Kept separate from Embedder so a host can generate and review them as a
    step of its own, before anything is indexed.
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        context: dict,
        path: str | Path | None = None,
    ):
        self.knowledge_graph = knowledge_graph
        self.context = context
        self.path = Path(path or config.CONCEPT_DESCRIPTIONS_PATH)

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        with self.path.open(encoding="utf-8") as f:
            return json.load(f)

    def save(self, descriptions: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(descriptions, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    def ensure(
        self,
        descriptions: dict[str, str] | None = None,
        concepts: list[str] | None = None,
        overwrite: bool = False,
    ) -> dict[str, str]:
        descriptions = self.load() if descriptions is None else dict(descriptions)
        targets = concepts if concepts is not None else self.knowledge_graph.taggable_concepts

        pending = list(targets) if overwrite else [c for c in targets if c not in descriptions]
        if not pending:
            logger.info(f"Loaded {len(targets)} taggable concept description(s) from cache")
            return descriptions

        logger.info(f"Generating {len(pending)} concept description(s)...")
        with progress.step(
            "descriptions", "Generando descripciones de conceptos", total=len(pending)
        ) as reporter:
            for i, concept in enumerate(pending, 1):
                progress.checkpoint()
                logger.info(f"[{i}/{len(pending)}] Generating description: {concept}")
                reporter.tick(i, detail=concept)
                try:
                    descriptions[concept] = self.describe(concept)
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.warning(f"Falling back to legacy describe for '{concept}': {e}")
                    descriptions[concept] = self.simple_describe(concept)
                # Checkpoint after every concept: a cancelled run keeps what it wrote.
                self.save(descriptions)

        logger.success(f"Saved {len(descriptions)} concept descriptions to cache")
        return descriptions

    def describe(self, concept: str) -> str:
        domain = self.knowledge_graph.concept_domain[concept]
        relations = self.collect_relations(concept)
        siblings = [
            c
            for c in self.knowledge_graph.concepts_by_domains[domain]
            if c != concept and c not in self.knowledge_graph.generic_non_taggable_concepts
        ]

        prompt = concept_description_prompt(
            concept=concept,
            domain=domain,
            relations=relations,
            siblings=siblings,
            context=self.context,
        )
        response = inference.generate(
            model=config.CONTENT_FORMATTING_LLM, think=False, prompt=prompt
        ).response
        return response.strip()

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

    def simple_describe(self, concept: str) -> str:
        domain = self.knowledge_graph.concept_domain[concept]
        lines = [f'Concepto: "{concept}".', f'Dominio: "{domain}"']
        lines.extend(
            f'{verb}: {", ".join(neighbors)}.'
            for verb, neighbors in self.collect_relations(concept).items()
        )
        return "\n".join(lines)


class Embedder:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_model: str,
        primary_field: str,
        context: dict,
        descriptions_path: str | Path | None = None,
        concepts_cache_path: str | Path | None = None,
        exemplars_bank_cache_path: str | Path | None = None,
    ):
        self.knowledge_graph = knowledge_graph
        self.embedding_model = embedding_model
        self.primary_field = primary_field
        self.context = context

        self.descriptions_path = Path(descriptions_path or config.CONCEPT_DESCRIPTIONS_PATH)
        self.concepts_cache_path = Path(concepts_cache_path or config.CONCEPTS_EMBEDDINGS_PATH)
        self.exemplars_bank_cache_path = Path(
            exemplars_bank_cache_path or config.EXEMPLARS_BANK_EMBEDDINGS_PATH
        )

        self.similarity_threshold = config.EMBEDDER_SIMILARITY_THRESHOLD
        self.relative_margin = config.EMBEDDER_RELATIVE_MARGIN
        self.description_weight = config.EMBEDDER_DESCRIPTION_WEIGHT

        self.concepts_index: dict[str, np.ndarray] = {}
        self.exemplars_bank_index: dict[str, np.ndarray] = {}
        self.concept_descriptions: dict[str, str] = {}
        self.exemplars_bank: dict[str, dict] = {}
        self._cached_exemplars_bank_fingerprint: str | None = None
        self._cached_text_fingerprints: dict[str, str] = {}
        self._embed_cache: dict[str, np.ndarray] = {}

        self._concept_keys: list[str] = []
        self._concept_matrix: np.ndarray = np.zeros((0, 0))
        self._exemplar_keys: list[str] = []
        self._exemplar_matrix: np.ndarray = np.zeros((0, 0))
        self._exemplar_rows_by_concept: dict[str, list[int]] = {}

        self.describer = ConceptDescriber(knowledge_graph, context, self.descriptions_path)
        self._ensure_descriptions()
        self._ensure_concepts_index()

        self.merged_index: dict[str, np.ndarray] = dict(self.concepts_index)
        self._load_previous_bank_index()
        self._rebuild_matrices()

    # SETUP ---------------------------------------------------------------------------------------

    def _ensure_concepts_index(self) -> None:
        if self._is_concept_cache_valid():
            self._load_concept_cache()
            logger.info(f"Loaded concepts index from cache ({len(self.concepts_index)} concepts)")
            return
        logger.info("Building concepts index...")
        self.init_index_with_concepts()
        self._save_concept_cache()
        logger.info(f"Saved concepts index cache ({len(self.concepts_index)} concepts)")

    # The bank index persisted by the previous run is a warm start for this run's tagging:
    # enrich_index_with_content re-embeds and re-merges it once the current bank is known.
    def _load_previous_bank_index(self) -> None:
        if not self.exemplars_bank_cache_path.exists():
            logger.warning(
                "Exemplars bank embeddings cache not found - call enrich_index_with_content to generate it."
            )
            return
        self._load_exemplars_bank_cache()
        self._merge_into_index()
        logger.info(
            f"Loaded exemplars bank cache and merged index ({len(self.exemplars_bank_index)} items)"
        )

    # FINGERPRINTS --------------------------------------------------------------------------------

    def _embedding_fingerprint(self) -> str:
        return "::".join(
            [
                self.embedding_model,
                config.EMBEDDING_QUERY_PREFIX,
                config.EMBEDDING_DOCUMENT_PREFIX,
            ]
        )

    @staticmethod
    def _text_fingerprint(text: str) -> str:
        return hashlib.md5((text or "").encode()).hexdigest()

    def _concept_fingerprint(self) -> str:
        taggable = self.knowledge_graph.taggable_concepts
        payload = json.dumps(
            {
                "concepts": sorted(taggable),
                "descriptions": {c: self.concept_descriptions[c] for c in sorted(taggable) if c in self.concept_descriptions},
            },
            ensure_ascii=False,
        )
        return hashlib.md5(f"{self._embedding_fingerprint()}::{payload}".encode()).hexdigest()

    def _exemplars_bank_fingerprint(self) -> str:
        entries = sorted(
            (
                ex_id,
                self._text_fingerprint(ex[self.primary_field]),
                sorted(ex.get("concepts", [])),
                ex.get("primary_concept") or "",
            )
            for ex_id, ex in self.exemplars_bank.items()
        )
        entries_serialized = json.dumps(entries, ensure_ascii=False)
        return hashlib.md5(
            f"{self._embedding_fingerprint()}::{entries_serialized}".encode()
        ).hexdigest()

    # CONCEPT CACHE --------------------------------------------------------------------

    def _is_concept_cache_valid(self) -> bool:
        if not self.concepts_cache_path.exists():
            return False
        try:
            data = np.load(self.concepts_cache_path, allow_pickle=True)
            return str(data["fingerprint"]) == self._concept_fingerprint()
        except Exception:
            return False

    def _load_concept_cache(self) -> None:
        data = np.load(self.concepts_cache_path, allow_pickle=True)
        self.concepts_index = dict(zip(data["keys"], data["vectors"]))

    def _save_concept_cache(self) -> None:
        self.concepts_cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self.concepts_cache_path,
            keys=list(self.concepts_index.keys()),
            vectors=np.array(list(self.concepts_index.values())),
            fingerprint=self._concept_fingerprint(),
        )

    # EXEMPLARS BANK CACHE -------------------------------------------------------------

    def _load_exemplars_bank_cache(self) -> None:
        data = np.load(self.exemplars_bank_cache_path, allow_pickle=True)
        self.exemplars_bank_index = dict(zip(data["keys"], data["vectors"]))
        assignments = json.loads(str(data["assignments"]))
        self.exemplars_bank = {
            ex_id: {
                "concepts": entry.get("concepts", []),
                "primary_concept": entry.get("primary_concept"),
            }
            for ex_id, entry in assignments.items()
        }
        self._cached_text_fingerprints = {
            ex_id: entry.get("text", "") for ex_id, entry in assignments.items()
        }
        self._cached_exemplars_bank_fingerprint = str(data["fingerprint"])

    def _save_exemplars_bank_cache(self) -> None:
        self.exemplars_bank_cache_path.parent.mkdir(parents=True, exist_ok=True)
        assignments = {
            ex_id: {
                "concepts": sorted(ex.get("concepts", [])),
                "primary_concept": ex.get("primary_concept"),
                "text": self._text_fingerprint(ex[self.primary_field]),
            }
            for ex_id, ex in self.exemplars_bank.items()
        }
        np.savez(
            self.exemplars_bank_cache_path,
            keys=list(self.exemplars_bank_index.keys()),
            vectors=np.array(list(self.exemplars_bank_index.values())),
            assignments=json.dumps(assignments, ensure_ascii=False),
            fingerprint=self._exemplars_bank_fingerprint(),
        )

    # CONCEPT DESCRIPTIONS ------------------------------------------------------------------------

    def _ensure_descriptions(self) -> None:
        self.concept_descriptions = self.describer.ensure()

    # INDICES -------------------------------------------------------------------------------

    def init_index_with_concepts(self) -> None:
        concepts = self.knowledge_graph.taggable_concepts
        with progress.step("index_concepts", "Indexando conceptos", total=len(concepts)) as reporter:
            vectors = self._embed_many(
                [self.concept_descriptions[c] for c in concepts], "document", reporter
            )
        self.concepts_index = dict(zip(concepts, vectors))

    def enrich_index_with_content(self, annotated_bank: dict) -> None:
        cached_vectors = self.exemplars_bank_index
        cached_texts = self._cached_text_fingerprints

        self.exemplars_bank = annotated_bank
        new_fingerprint = self._exemplars_bank_fingerprint()

        if self._cached_exemplars_bank_fingerprint == new_fingerprint and cached_vectors:
            logger.info("Exemplars bank index already up to date; skipping re-embedding.")
            return

        reusable = {
            ex_id: cached_vectors[ex_id]
            for ex_id, ex in annotated_bank.items()
            if ex_id in cached_vectors
            and cached_texts.get(ex_id) == self._text_fingerprint(ex[self.primary_field])
        }
        pending = [ex_id for ex_id in annotated_bank if ex_id not in reusable]

        if pending:
            logger.info(
                f"Embedding {len(pending)} exemplars bank example(s) "
                f"({len(reusable)} reused from cache)..."
            )
            with progress.step(
                "embed_bank", "Indexando el banco de ejemplos", total=len(pending)
            ) as reporter:
                vectors = self._embed_many(
                    [annotated_bank[ex_id][self.primary_field] for ex_id in pending],
                    "document",
                    reporter,
                )
            reusable.update(zip(pending, vectors))

        self.exemplars_bank_index = {ex_id: reusable[ex_id] for ex_id in annotated_bank}
        self._save_exemplars_bank_cache()
        self._cached_text_fingerprints = {
            ex_id: self._text_fingerprint(ex[self.primary_field])
            for ex_id, ex in annotated_bank.items()
        }
        self._cached_exemplars_bank_fingerprint = new_fingerprint
        self._merge_into_index()
        self._rebuild_matrices()
        logger.info(
            f"Saved exemplars bank cache and merged index ({len(self.exemplars_bank_index)} items)"
        )

    def _merge_into_index(self) -> None:
        alpha = self.description_weight
        for concept in self.knowledge_graph.taggable_concepts:
            description_vec = self.concepts_index[concept]

            example_vecs = [
                self.exemplars_bank_index[ex_id]
                for ex_id, ex in self.exemplars_bank.items()
                if concept in ex.get("concepts", []) and ex_id in self.exemplars_bank_index
            ]

            if not example_vecs:
                self.merged_index[concept] = description_vec
                continue

            examples_centroid = self._l2_normalize(np.mean(example_vecs, axis=0))
            self.merged_index[concept] = self._l2_normalize(
                alpha * description_vec + (1.0 - alpha) * examples_centroid
            )

    def _rebuild_matrices(self) -> None:
        self._concept_keys = list(self.merged_index.keys())
        self._concept_matrix = (
            np.stack([self.merged_index[c] for c in self._concept_keys])
            if self._concept_keys
            else np.zeros((0, 0))
        )

        self._exemplar_keys = [
            ex_id
            for ex_id in self.exemplars_bank_index
            if (self.exemplars_bank.get(ex_id) or {}).get("primary_concept")
        ]
        self._exemplar_matrix = (
            np.stack([self.exemplars_bank_index[ex_id] for ex_id in self._exemplar_keys])
            if self._exemplar_keys
            else np.zeros((0, 0))
        )
        self._exemplar_rows_by_concept = {}
        for row, ex_id in enumerate(self._exemplar_keys):
            concept = self.exemplars_bank[ex_id]["primary_concept"]
            self._exemplar_rows_by_concept.setdefault(concept, []).append(row)

    # VECTOR MATH -----------------------------------------------------------------------------

    @staticmethod
    def _prefix(kind: str) -> str:
        if kind == "query":
            return config.EMBEDDING_QUERY_PREFIX
        return config.EMBEDDING_DOCUMENT_PREFIX

    def _embed(self, text: str, kind: str) -> np.ndarray:
        key = self._prefix(kind) + text
        cached = self._embed_cache.get(key)
        if cached is not None:
            return cached
        raw = inference.embed(model=self.embedding_model, text=key)
        vector = self._l2_normalize(np.array(raw, dtype=np.float32))
        self._embed_cache[key] = vector
        return vector

    def _embed_many(self, texts: list[str], kind: str, reporter=None) -> list[np.ndarray]:
        keys = [self._prefix(kind) + t for t in texts]
        pending = [k for k in dict.fromkeys(keys) if k not in self._embed_cache]

        done = 0
        for start in range(0, len(pending), config.EMBEDDING_BATCH_SIZE):
            progress.checkpoint()
            batch = pending[start : start + config.EMBEDDING_BATCH_SIZE]
            vectors = inference.embed_batch(model=self.embedding_model, texts=batch)
            for key, vector in zip(batch, vectors):
                self._embed_cache[key] = self._l2_normalize(np.array(vector, dtype=np.float32))
            done += len(batch)
            if reporter is not None:
                reporter.tick(done)

        return [self._embed_cache[k] for k in keys]

    def _l2_normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    # RETRIEVAL -----------------------------------------------------------------------------

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        scores = self._score_concepts(self._embed(text, "query"))
        if not scores:
            return []

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if ranked[0][1] < self.similarity_threshold:
            return []

        cutoff = ranked[0][1] - self.relative_margin
        return [(c, s) for c, s in ranked[:k] if s >= cutoff]

    def _score_concepts(self, vec: np.ndarray) -> dict[str, float]:
        if not self._concept_keys:
            return {}

        centroid_scores = self._concept_matrix @ vec
        scores = {c: float(s) for c, s in zip(self._concept_keys, centroid_scores)}

        if not self._exemplar_keys:
            return scores

        exemplar_scores = self._exemplar_matrix @ vec
        for concept, rows in self._exemplar_rows_by_concept.items():
            if concept in scores:
                scores[concept] = max(scores[concept], float(exemplar_scores[rows].max()))
        return scores
