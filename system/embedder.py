import hashlib
import json
from pathlib import Path

import numpy as np
from loguru import logger

from . import config, inference
from .knowledge_graph import KnowledgeGraph
from .prompts import concept_description_prompt


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

        self.concepts_index: dict[str, np.ndarray] = {}
        self.exemplars_bank_index: dict[str, np.ndarray] = {}
        self.concept_descriptions: dict[str, str] = {}
        self.exemplars_bank: dict[str, dict] = {}
        self._cached_exemplars_bank_fingerprint: str | None = None

        self._ensure_descriptions()
        self._ensure_concepts_index()

        self.merged_index: dict[str, np.ndarray] = dict(self.concepts_index)
        self._load_previous_bank_index()

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

    def _concept_fingerprint(self) -> str:
        taggable = self.knowledge_graph.taggable_concepts
        payload = json.dumps(
            {
                "concepts": sorted(taggable),
                "descriptions": {c: self.concept_descriptions[c] for c in sorted(taggable) if c in self.concept_descriptions},
            },
            ensure_ascii=False,
        )
        return hashlib.md5(f"{self.embedding_model}::{payload}".encode()).hexdigest()

    def _exemplars_bank_fingerprint(self) -> str:
        entries = sorted(
            (ex_id, ex[self.primary_field], sorted(ex.get("concepts", [])))
            for ex_id, ex in self.exemplars_bank.items()
        )
        entries_serialized = json.dumps(entries, ensure_ascii=False)
        return hashlib.md5(f"{self.embedding_model}::{entries_serialized}".encode()).hexdigest()

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
        self.exemplars_bank = json.loads(str(data["assignments"]))
        self._cached_exemplars_bank_fingerprint = str(data["fingerprint"])

    def _save_exemplars_bank_cache(self) -> None:
        self.exemplars_bank_cache_path.parent.mkdir(parents=True, exist_ok=True)
        assignments = {
            ex_id: {"concepts": sorted(ex.get("concepts", []))}
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
        if self.descriptions_path.exists():
            with self.descriptions_path.open(encoding="utf-8") as f:
                self.concept_descriptions = json.load(f)

        missing = [
            c for c in self.knowledge_graph.taggable_concepts
            if c not in self.concept_descriptions
        ]
        if not missing:
            logger.info(
                f"Loaded {len(self.knowledge_graph.taggable_concepts)} taggable concept descriptions from cache"
            )
            return

        logger.info(f"Generating {len(missing)} concept description(s)...")
        for i, concept in enumerate(missing, 1):
            logger.info(f"[{i}/{len(missing)}] Generating description: {concept}")
            try:
                self.concept_descriptions[concept] = self._generate_description(concept)
            except Exception as e:
                logger.warning(f"Falling back to legacy describe for '{concept}': {e}")
                self.concept_descriptions[concept] = self._simple_describe(concept)

        self.descriptions_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self.descriptions_path.open("w", encoding="utf-8") as f:
            json.dump(self.concept_descriptions, f, ensure_ascii=False, indent=2)
        logger.success(f"Saved {len(self.concept_descriptions)} concept descriptions to cache")

    def _generate_description(self, concept: str) -> str:
        domain = self.knowledge_graph.concept_domain[concept]
        relations = self._collect_relations(concept)
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
        response = inference.generate(model=config.CONTENT_FORMATTING_LLM, think=False, prompt=prompt).response
        return response.strip()

    def _collect_relations(self, concept: str) -> dict[str, list[str]]:
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

    def _simple_describe(self, concept: str) -> str:
        domain = self.knowledge_graph.concept_domain[concept]
        lines = [f'Concepto: "{concept}".', f'Dominio: "{domain}"']
        lines.extend(
            f'{verb}: {", ".join(neighbors)}.'
            for verb, neighbors in self._collect_relations(concept).items()
        )
        return "\n".join(lines)

    # INDICES -------------------------------------------------------------------------------

    def init_index_with_concepts(self) -> None:
        for concept in self.knowledge_graph.taggable_concepts:
            self.concepts_index[concept] = self._embed(self.concept_descriptions[concept])

    def enrich_index_with_content(self, annotated_bank: dict) -> None:
        self.exemplars_bank = annotated_bank
        new_fingerprint = self._exemplars_bank_fingerprint()

        if self._cached_exemplars_bank_fingerprint == new_fingerprint and self.exemplars_bank_index:
            logger.info("Exemplars bank index already up to date; skipping re-embedding.")
            return

        self.exemplars_bank_index = {}
        logger.info(f"Embedding {len(annotated_bank)} exemplars bank examples...")

        for content_id, content in annotated_bank.items():
            self.exemplars_bank_index[content_id] = self._embed(content[self.primary_field])

        self._save_exemplars_bank_cache()
        self._cached_exemplars_bank_fingerprint = new_fingerprint
        self._merge_into_index()
        logger.info(
            f"Saved exemplars bank cache and merged index ({len(self.exemplars_bank_index)} items)"
        )

    def _merge_into_index(self) -> None:
        for concept in self.knowledge_graph.taggable_concepts:
            name_vec = self.concepts_index[concept]

            example_vecs = [
                self.exemplars_bank_index[ex_id]
                for ex_id, ex in self.exemplars_bank.items()
                if concept in ex.get("concepts", []) and ex_id in self.exemplars_bank_index
            ]

            all_vecs = [name_vec] + example_vecs
            self.merged_index[concept] = self._l2_normalize(np.mean(all_vecs, axis=0))

    # VECTOR MATH -----------------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        resp = inference.embed(model=self.embedding_model, text=text)
        return self._l2_normalize(np.array(resp))

    def _l2_normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.dot(vec_a, vec_b))

    # RETRIEVAL -----------------------------------------------------------------------------

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        vec = self._embed(text)
        scores = sorted(
            ((c, self.cosine_similarity(vec, v)) for c, v in self.merged_index.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(c, s) for c, s in scores[:k] if s >= self.similarity_threshold]
