import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
from loguru import logger

from . import config, inference, progress
from .knowledge_graph import KnowledgeGraph
from .prompts import concept_description_prompt


# El fichero de descripciones es una caché {concepto: texto} y nada más: leerlo o
# escribirlo no necesita ni el grafo ni el perfil de ejemplares. Vive fuera de
# `ConceptDescriber` porque exigir el describer completo para tocarlo acoplaba la lectura
# del grafo a un artefacto del que el grafo no depende — y esa es exactamente la razón por
# la que la pantalla del grafo respondía 404 mientras faltaba el perfil.
def load_descriptions(path: str | Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_descriptions(path: str | Path, descriptions: dict[str, str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _embed_normalized(texts: list[str], what: str):
    try:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), config.EMBEDDING_BATCH_SIZE):
            progress.checkpoint()
            vectors.extend(
                inference.embed_batch(
                    model=config.EMBEDDING_LLM,
                    texts=texts[start : start + config.EMBEDDING_BATCH_SIZE],
                )
            )
    except progress.Cancelled:
        raise
    except Exception as e:
        logger.warning(f"No se pudo vectorizar {what} ({e}); se sigue sin esa señal")
        return None

    matrix = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


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
        path: str | Path,
        siblings_top_k: int = config.DESCRIPTION_SIBLINGS_TOP_K,
        collision_similarity: float = config.DESCRIPTION_COLLISION_SIMILARITY,
    ):
        self.knowledge_graph = knowledge_graph
        self.context = context
        self.path = Path(path)
        self.siblings_top_k = siblings_top_k
        self.collision_similarity = collision_similarity
        self._name_vectors: dict[str, np.ndarray] | None = None

    def load(self) -> dict[str, str]:
        return load_descriptions(self.path)

    def save(self, descriptions: dict[str, str]) -> None:
        save_descriptions(self.path, descriptions)

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
            "domain": self.knowledge_graph.concept_domain[concept],
            "relations": {v: sorted(ns) for v, ns in self.collect_relations(concept).items()},
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
        self.fingerprints_path.parent.mkdir(parents=True, exist_ok=True)
        with self.fingerprints_path.open("w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2, sort_keys=True)

    def _pending(
        self, targets: list[str], descriptions: dict[str, str], current: dict[str, str]
    ) -> list[str]:
        stored = self._load_fingerprints()
        missing = [c for c in targets if c not in descriptions]
        stale = [
            c
            for c in targets
            if c in descriptions and c in stored and stored[c] != current[c]
        ]
        if stale:
            logger.info(
                f"{len(stale)} descripción(es) quedaron obsoletas al cambiar el grafo; "
                "se reescriben"
            )
        return missing + stale

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
            logger.success(
                f"{written} descripción(es) escritas; {len(descriptions)} en la caché"
            )
        return descriptions

    def _write(
        self,
        plan: list[str],
        descriptions: dict[str, str],
        against: dict[str, list[str]] | None = None,
    ) -> None:
        with progress.step(
            "descriptions", "Generando descripciones de conceptos", total=len(plan)
        ) as reporter:
            for i, concept in enumerate(plan, 1):
                progress.checkpoint()
                reporter.tick(i, detail=concept)
                try:
                    descriptions[concept] = self.describe(
                        concept, descriptions, against=(against or {}).get(concept)
                    )
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.warning(f"[{concept}] descripción de reserva, sin modelo: {e}")
                    descriptions[concept] = self.simple_describe(concept)
                # Checkpoint after every concept: a cancelled run keeps what it wrote.
                self.save(descriptions)

    def _by_domain(self, concepts: list[str]) -> list[str]:
        return sorted(concepts, key=lambda c: (self.knowledge_graph.concept_domain[c], c))

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

        prompt = concept_description_prompt(
            concept=concept,
            domain=domain,
            relations=relations,
            siblings=siblings,
            context=self.context,
        )
        response = inference.generate(
            model=config.DESCRIPTION_GENERATION_LLM, think=False, prompt=prompt
        ).response
        return response.strip()

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
            matrix = _embed_normalized(concepts, "concept names")
            self._name_vectors = (
                {} if matrix is None else dict(zip(concepts, matrix))
            )
        return self._name_vectors or None

    # Collisions are looked for across ALL concepts, not just within a domain: the pairs
    # that hurt retrieval are the ones the index cannot separate, and the domain partition
    # has no say in that (`Concatenación` and `operaciones con cadenas` landed in different
    # domains and still scored 0.896).
    def _collisions(self, descriptions: dict[str, str], targets: list[str]) -> dict[str, list[str]]:
        written = [c for c in targets if descriptions.get(c)]
        if len(written) < 2:
            return {}
        matrix = _embed_normalized([descriptions[c] for c in written], "descriptions")
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
        embed_text: Callable[[dict], str],
        embed_signature: str,
        context: dict,
        descriptions_path: str | Path,
        concepts_cache_path: str | Path,
        exemplars_bank_cache_path: str | Path,
    ):
        self.knowledge_graph = knowledge_graph
        self.embedding_model = embedding_model
        self.embed_text = embed_text
        self.embed_signature = embed_signature
        self.context = context

        self.descriptions_path = Path(descriptions_path)
        self.concepts_cache_path = Path(concepts_cache_path)
        self.exemplars_bank_cache_path = Path(exemplars_bank_cache_path)

        self.similarity_threshold = config.EMBEDDER_SIMILARITY_THRESHOLD
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
            logger.info(
                f"Índice de conceptos reutilizado de la caché ({len(self.concepts_index)} concepto(s))"
            )
            return
        logger.info("Construyendo el índice de conceptos")
        self.init_index_with_concepts()
        self._save_concept_cache()

    # The bank index persisted by the previous run is a warm start for this run's tagging:
    # enrich_index_with_content re-embeds and re-merges it once the current bank is known.
    def _load_previous_bank_index(self) -> None:
        if not self.exemplars_bank_cache_path.exists():
            return
        self._load_exemplars_bank_cache()
        self._merge_into_index()

    # FINGERPRINTS --------------------------------------------------------------------------------

    # `embed_signature` is which fields of each item type are indexed. It belongs here and
    # not only in the per-item text hash because the CONCEPT cache is fingerprinted by this
    # too: change the fields and the merged centroids change, while the descriptions that
    # built them do not.
    # Appended only when non-empty, so a profile that indexes primary fields alone produces
    # the exact string this used to produce and keeps its caches: a separator on its own is
    # enough to invalidate every vector for no change in the text they were built from.
    def _embedding_fingerprint(self) -> str:
        base = (
            f"{self.embedding_model}::{config.EMBEDDING_QUERY_PREFIX}"
            f"::{config.EMBEDDING_DOCUMENT_PREFIX}"
        )
        return f"{base}::{self.embed_signature}" if self.embed_signature else base

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
                self._text_fingerprint(self.embed_text(ex)),
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
                "text": self._text_fingerprint(self.embed_text(ex)),
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
            logger.info("Índice del banco al día; no hay nada que vectorizar")
            return

        reusable = {
            ex_id: cached_vectors[ex_id]
            for ex_id, ex in annotated_bank.items()
            if ex_id in cached_vectors
            and cached_texts.get(ex_id) == self._text_fingerprint(self.embed_text(ex))
        }
        pending = [ex_id for ex_id in annotated_bank if ex_id not in reusable]

        if pending:
            logger.info(
                f"Vectorizando {len(pending)} ítem(s) del banco "
                f"({len(reusable)} reutilizados de la caché)"
            )
            with progress.step(
                "embed_bank", "Indexando el banco de ejemplos", total=len(pending)
            ) as reporter:
                vectors = self._embed_many(
                    [self.embed_text(annotated_bank[ex_id]) for ex_id in pending],
                    "document",
                    reporter,
                )
            reusable.update(zip(pending, vectors))

        self.exemplars_bank_index = {ex_id: reusable[ex_id] for ex_id in annotated_bank}
        self._save_exemplars_bank_cache()
        self._cached_text_fingerprints = {
            ex_id: self._text_fingerprint(self.embed_text(ex))
            for ex_id, ex in annotated_bank.items()
        }
        self._cached_exemplars_bank_fingerprint = new_fingerprint
        self._merge_into_index()
        self._rebuild_matrices()

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

    def _pending_keys(self, keys: list[str]) -> list[str]:
        return [k for k in dict.fromkeys(keys) if k not in self._embed_cache]

    def _embed_many(self, texts: list[str], kind: str, reporter=None) -> list[np.ndarray]:
        keys = [self._prefix(kind) + t for t in texts]
        pending = self._pending_keys(keys)

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

    def prefetch_queries(self, texts: list[str]) -> None:
        pending = self._pending_keys([self._prefix("query") + t for t in texts])
        if not pending:
            return
        logger.info(f"Vectorizando {len(pending)} enunciado(s) para la recuperación")
        with progress.step(
            "embed_queries", "Vectorizando los enunciados", total=len(pending)
        ) as reporter:
            self._embed_many(texts, "query", reporter)

    # Ranked against the concept DESCRIPTIONS, never the merged centroids: the centroid
    # is built from these same exemplars, so ranking them by it would be circular.
    def rank_exemplars(self, concepts: list[str], exemplar_ids: list[str]) -> list[str]:
        vectors = [self.concepts_index[c] for c in concepts if c in self.concepts_index]
        if not vectors:
            return list(exemplar_ids)

        matrix = np.stack(vectors)
        scored = []
        for ex_id in exemplar_ids:
            vector = self.exemplars_bank_index.get(ex_id)
            scored.append((float((matrix @ vector).max()) if vector is not None else -1.0, ex_id))
        scored.sort(key=lambda pair: -pair[0])
        return [ex_id for _, ex_id in scored]

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        scores = self._score_concepts(self._embed(text, "query"))
        if not scores:
            return []

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if ranked[0][1] < self.similarity_threshold:
            return []

        return ranked[:k]

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
