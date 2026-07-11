import hashlib
import json

from . import config
import numpy as np
import ollama
from loguru import logger

from system.knowledge_graph import KnowledgeGraph
from .prompts import concept_descrition_prompt


class Embedder:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_model: str,
        primary_field: str,
        context: dict,
    ):
        self.knowledge_graph = knowledge_graph
        self.embedding_model = embedding_model
        self.primary_field = primary_field
        self.context = context

        self.similarity_threshold = config.EMBEDDER_SIMILARITY_THRESHOLD

        self.concepts_index: dict[str, np.ndarray] = {}
        self.exemplars_bank_index: dict[str, np.ndarray] = {}
        self.concept_descriptions: dict[str, str] = {}

        self._load_or_generate_descriptions()

        if self._is_concept_cache_valid():
            self._load_concept_cache()
            logger.info(f"Loaded concepts index from cache ({len(self.concepts_index)} concepts)")
        else:
            logger.info("Building concepts index...")
            self.init_index_with_concepts()
            self._save_concept_cache()
            logger.info(f"Saved concepts index cache ({len(self.concepts_index)} concepts)")

        self.index: dict[str, np.ndarray] = dict(self.concepts_index)

        if config.EXEMPLARS_BANK_EMBEDDINGS_PATH.exists():
            self._load_exemplars_bank_cache()
            self._merge_into_index()
            logger.info(f"Loaded exemplars bank cache and merged index ({len(self.exemplars_bank_index)} items)")
        else:
            logger.warning("Exemplars bank embeddings cache not found - call enrich_index_with_content to generate it.")

    # FIGERPRINTS ---------------------------------------------------------------------------------

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

    # CONCEPT CACHE VALIDATION --------------------------------------------------------------------

    def _is_concept_cache_valid(self) -> bool:
        if not config.CONCEPTS_EMBEDDINGS_PATH.exists():
            return False
        try:
            data = np.load(config.CONCEPTS_EMBEDDINGS_PATH, allow_pickle=True)
            return str(data["fingerprint"]) == self._concept_fingerprint()
        except Exception:
            return False

    def _load_concept_cache(self) -> None:
        data = np.load(config.CONCEPTS_EMBEDDINGS_PATH, allow_pickle=True)
        self.concepts_index = dict(zip(data["keys"], data["vectors"]))

    def _save_concept_cache(self) -> None:
        config.CONCEPTS_EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            config.CONCEPTS_EMBEDDINGS_PATH,
            keys=list(self.concepts_index.keys()),
            vectors=np.array(list(self.concepts_index.values())),
            fingerprint=self._concept_fingerprint(),
        )

    # EXEMPLARS BANK CACHE VALIDATION -------------------------------------------------------------

    def _is_exemplars_bank_cache_valid(self) -> bool:
        if not config.EXEMPLARS_BANK_EMBEDDINGS_PATH.exists():
            return False
        try:
            data = np.load(config.EXEMPLARS_BANK_EMBEDDINGS_PATH, allow_pickle=True)
            return str(data["fingerprint"]) == self._exemplars_bank_fingerprint()
        except Exception:
            return False

    def _load_exemplars_bank_cache(self) -> None:
        data = np.load(config.EXEMPLARS_BANK_EMBEDDINGS_PATH, allow_pickle=True)
        self.exemplars_bank_index = dict(zip(data["keys"], data["vectors"]))
        self.exemplars_bank = json.loads(str(data["assignments"]))
        self._cached_exemplars_bank_fingerprint = str(data["fingerprint"])

    def _save_exemplars_bank_cache(self) -> None:
        config.EXEMPLARS_BANK_EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        assignments = {
            ex_id: {"concepts": sorted(ex.get("concepts", []))}
            for ex_id, ex in self.exemplars_bank.items()
        }
        np.savez(
            config.EXEMPLARS_BANK_EMBEDDINGS_PATH,
            keys=list(self.exemplars_bank_index.keys()),
            vectors=np.array(list(self.exemplars_bank_index.values())),
            assignments=json.dumps(assignments, ensure_ascii=False),
            fingerprint=self._exemplars_bank_fingerprint(),
        )

    # CONCEPT DESCRIPTIONS ------------------------------------------------------------------------

    def _load_or_generate_descriptions(self) -> None:
        if config.CONCEPT_DESCRIPTIONS_PATH.exists():
            with config.CONCEPT_DESCRIPTIONS_PATH.open(encoding="utf-8") as f:
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

        config.CONCEPT_DESCRIPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.CONCEPT_DESCRIPTIONS_PATH.open("w", encoding="utf-8") as f:
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

        prompt = concept_descrition_prompt(
            concept=concept,
            domain=domain,
            relations=relations,
            siblings=siblings,
            context=self.context,
        )
        response = ollama.generate(model=config.CONTENT_FORMATTING_LLM, think=False, prompt=prompt).response
        return response.strip()

    def _collect_relations(self, concept: str) -> dict[str, list[str]]:
        relations: dict[str, list[str]] = {}
        for verb, graph in self.knowledge_graph.graphs.items():
            if concept not in graph:
                continue
            if graph.is_directed():
                successors = sorted(graph.successors(concept))
                predecessors = sorted(graph.predecessors(concept))
                if successors:
                    relations[f"este concepto {verb}"] = successors
                if predecessors:
                    relations[f"{verb} este concepto"] = predecessors
            else:
                nbrs = sorted(graph.neighbors(concept))
                if nbrs:
                    relations[verb] = nbrs
        return relations

    def _simple_describe(self, concept: str) -> str:
        kg = self.knowledge_graph
        domain = kg.concept_domain[concept]
        lines = [f'Concepto: "{concept}".', f'Dominio: "{domain}"']

        for verb, graph in kg.graphs.items():
            if not kg.details(verb).get("use_in_embedding", True):
                continue
            if graph.is_directed():
                forward = sorted(graph.predecessors(concept))
                backward = sorted(graph.successors(concept))
                if forward:
                    lines.append(f'Este concepto {verb}: {", ".join(forward)}.')
                for s in backward:
                    lines.append(f"{s} {verb} este concepto.")
            else:
                nbrs = sorted(graph.neighbors(concept))
                if nbrs:
                    lines.append(f'Este concepto {verb}: {", ".join(nbrs)}.')

        return "\n".join(lines)

    # BUILD INDICES -------------------------------------------------------------------------------

    def init_index_with_concepts(self) -> None:
        for concept in self.knowledge_graph.taggable_concepts:
            self.concepts_index[concept] = self._embed(self.concept_descriptions[concept])

    def enrich_index_with_content(self, annotated_bank: dict) -> None:
        self.exemplars_bank = annotated_bank
        new_fingerprint = self._exemplars_bank_fingerprint()

        if (
            getattr(self, "_cached_exemplars_bank_fingerprint", None) == new_fingerprint
            and self.exemplars_bank_index
        ):
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
            self.index[concept] = self._l2_normalize(np.mean(all_vecs, axis=0))

    # TECHNICAL STUFF -----------------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        resp = ollama.embeddings(model=self.embedding_model, prompt=text)["embedding"]
        return self._l2_normalize(np.array(resp))

    def _l2_normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.dot(vec_a, vec_b))

    # RETRIEVE  -----------------------------------------------------------------------------

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        vec = self._embed(text)
        scores = sorted(
            ((c, self.cosine_similarity(vec, v)) for c, v in self.index.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(c, s) for c, s in scores[:k] if s >= self.similarity_threshold]
