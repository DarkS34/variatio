import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import networkx as nx
from json_repair import repair_json
from loguru import logger

from .. import config, inference, progress
from ..prompts import (
    clean_graph_nodes_prompt,
    curate_graph_domains_prompt,
    extract_typed_graph_prompt,
    link_global_relations_prompt,
)
from ..relations import RelationSchema
from ..utils import parse_with_repair
from . import _source_docs

MIN_SINGULARIZE_LENGTH = 3

# Measured shares of a whole build, not guesses: extraction is one model call per chunk
# and dominates; linking, cleaning and curating are one big call each over the whole
# inventory, which is minutes of apparent silence unless the bar accounts for them.
BUILD_PHASES = (
    ("convert", "Convirtiendo los documentos del corpus", 8),
    ("extract", "Extrayendo conceptos y relaciones", 60),
    ("link", "Enlazando conceptos entre temas", 10),
    ("clean", "Fusionando duplicados y normalizando nombres", 11),
    ("curate", "Agrupando en dominios y tipando las relaciones", 11),
)


class KnowledgeGraphBuilder:
    def __init__(self, schema: RelationSchema | None = None, verbose: bool = True):
        self.schema = schema or config.RELATION_SCHEMA
        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.chunk_size = config.KG_BUILDER_CHUNK_SIZE

        logger.enable(__name__) if verbose else logger.disable(__name__)

        self._converter = None

    @property
    def converter(self):
        if self._converter is None:
            self._converter = _source_docs.default_converter(table_structure=False)
        return self._converter

    # PUBLIC API ----------------------------------------------------------------------------------

    def bootstrap(self) -> None:
        models = list(
            dict.fromkeys(
                (
                    config.KG_BUILDER_EXTRACTION_MODEL,
                    config.KG_BUILDER_CURATION_MODEL,
                    config.REPAIR_LLM,
                )
            )
        )
        logger.info(f"Preparing knowledge graph model(s): {', '.join(models)}")
        failed = [m for m in models if not inference.ensure_model(m)]
        if failed:
            raise RuntimeError(f"Failed to install model(s): {', '.join(failed)}")
        for model in models:
            progress.checkpoint()
            inference.warmup(model)
        logger.success("Knowledge graph models ready")

    def build(self, input_dir: str | Path) -> dict:
        self.bootstrap()

        staging = self.extract(input_dir)
        if not staging:
            raise RuntimeError(f"No knowledge graph could be extracted from: {input_dir}")

        progress.checkpoint()
        cleaned = self.clean(staging)

        progress.checkpoint()
        return self.curate(cleaned)

    # EXTRACTION ----------------------------------------------------------------------------------

    def extract(self, input_dir: str | Path, recursive: bool = False) -> dict:
        documents = self._convert_corpus(input_dir, recursive)
        if not documents:
            return {}

        concepts, relations = self._extract_documents(documents)
        if not concepts:
            logger.error("No concepts extracted from any file")
            return {}

        for source, _, target in relations:
            concepts.update((source, target))

        progress.checkpoint()
        progress.phase("link", f"{len(concepts)} concepto(s) en una sola pasada global")
        with progress.step("kg_link", "Enlazando conceptos entre temas"):
            before = len(relations)
            relations.update(tuple(r) for r in self._link_global(sorted(concepts)))
            logger.info(f"Global linking pass added {len(relations) - before} relation(s)")
        progress.advance(1.0)

        staging = self._assemble(concepts, relations)
        logger.success(
            f"Extraction done — {len(staging['entities'])} entity(ies), "
            f"{len(staging['relations'])} relation(s)"
        )
        return staging

    # Every document is converted and chunked up front so the extraction bar knows its
    # own total: a per-file bar cannot say how much of the corpus is left, because a
    # 40-chunk lecture and a 3-chunk one weigh the same in it.
    def _convert_corpus(
        self, input_dir: str | Path, recursive: bool
    ) -> list[tuple[str, list[str]]]:
        files = _source_docs.list_source_files(input_dir, recursive=recursive)
        if not files:
            logger.error(f"No supported files found in: {input_dir}")
            return []

        logger.info(f"Found {len(files)} file(s) - converting the corpus to markdown")
        progress.phase("convert", f"0/{len(files)} documento(s)")

        documents: list[tuple[str, list[str]]] = []
        with progress.step(
            "kg_convert", "Convirtiendo los documentos del corpus", len(files)
        ) as reporter:
            for idx, file_path in enumerate(files, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=file_path.name)
                progress.advance(
                    (idx - 1) / len(files), f"{file_path.name} ({idx}/{len(files)})"
                )
                try:
                    text = _source_docs.to_markdown(self.converter, file_path)
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"[{file_path.name}] skipped: {e}")
                    continue

                chunks = _source_docs.chunk_text(text, self.chunk_size)
                if not chunks:
                    logger.warning(f"[{file_path.name}] produced no text")
                    continue
                documents.append((file_path.name, chunks))
                logger.info(f"[{idx}/{len(files)} {file_path.name}] {len(chunks)} chunk(s)")

        progress.advance(1.0, f"{len(documents)} documento(s) listos")
        return documents

    def _extract_documents(
        self, documents: list[tuple[str, list[str]]]
    ) -> tuple[set[str], set[tuple[str, str, str]]]:
        total = sum(len(chunks) for _, chunks in documents)
        logger.info(f"Extracting from {total} chunk(s) across {len(documents)} document(s)")
        progress.phase("extract", f"0/{total} fragmento(s)")

        concepts: set[str] = set()
        relations: set[tuple[str, str, str]] = set()
        done = 0

        with progress.step(
            "kg_extract", "Extrayendo conceptos y relaciones", total
        ) as reporter:
            for name, chunks in documents:
                for ci, chunk in enumerate(chunks, 1):
                    progress.checkpoint()
                    done += 1
                    reporter.tick(
                        done,
                        detail=(
                            f"{name} · fragmento {ci}/{len(chunks)} · "
                            f"{len(concepts)} concepto(s), {len(relations)} relación(es)"
                        ),
                    )
                    progress.advance(
                        (done - 1) / total,
                        f"fragmento {done}/{total} · {len(concepts)} concepto(s)",
                    )
                    tag = f"[{name} · chunk {ci}/{len(chunks)}] "
                    chunk_concepts, chunk_relations = self._extract_from_chunk(chunk, tag)
                    concepts.update(chunk_concepts)
                    relations.update(tuple(r) for r in chunk_relations)
                    progress.emit(
                        "artifact.progress",
                        name="knowledge_graph",
                        count=len(concepts),
                        detail=f"{len(relations)} relación(es)",
                    )

        progress.advance(1.0, f"{len(concepts)} concepto(s), {len(relations)} relación(es)")
        return concepts, relations

    def _extract_from_chunk(self, chunk: str, log_prefix: str) -> tuple[list[str], list[list[str]]]:
        prompt = extract_typed_graph_prompt(chunk, self.schema)
        response = inference.generate(
            model=config.KG_BUILDER_EXTRACTION_MODEL, prompt=prompt, think=False
        ).response
        raw = self._parse_object(response, log_prefix)
        if raw is None:
            return [], []
        concepts = [c.strip() for c in raw.get("concepts", []) if isinstance(c, str) and c.strip()]
        relations = self._valid_relations(raw.get("relations", []), allowed=None)
        return concepts, relations

    def _link_global(self, inventory: list[str]) -> list[list[str]]:
        if len(inventory) < 2:
            return []
        prompt = link_global_relations_prompt(self._concepts_block(inventory), self.schema)
        response = inference.generate(
            model=config.KG_BUILDER_EXTRACTION_MODEL, prompt=prompt, think=False
        ).response
        raw = self._parse_object(response, "[global] ")
        if raw is None:
            return []
        return self._valid_relations(raw.get("relations", []), allowed=set(inventory))

    def _parse_object(self, response: str, log_prefix: str) -> dict | None:
        result, error = parse_with_repair(
            response,
            _parse_json_object,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="object",
            log_prefix=log_prefix,
        )
        if result is None:
            logger.warning(f"{log_prefix}unrecoverable JSON: {error}")
        return result

    def _valid_relations(self, raw: list, allowed: set[str] | None) -> list[list[str]]:
        out = []
        for triple in raw or []:
            if not (isinstance(triple, list) and len(triple) == 3):
                continue
            if not all(isinstance(x, str) for x in triple):
                continue
            source, relation, target = (x.strip() for x in triple)
            if not (source and target) or source == target or relation not in self.schema:
                continue
            if allowed is not None and (source not in allowed or target not in allowed):
                continue
            out.append([source, relation, target])
        return out

    @staticmethod
    def _concepts_block(concepts: list[str]) -> str:
        return "\n".join(f"- {c}" for c in concepts)

    @staticmethod
    def _assemble(concepts: set[str], relations: set[tuple[str, str, str]]) -> dict:
        rels = sorted(list(r) for r in relations)
        return {
            "entities": sorted(concepts),
            "edges": sorted({r[1] for r in rels}),
            "relations": rels,
        }

    # CLEANUP -------------------------------------------------------------------------------------

    # clean proposes a deduplicated, denoised graph; nothing reaches disk until curate
    # writes the draft, so a build leaves no intermediate files behind.
    def clean(self, staging: dict) -> dict:
        progress.phase("clean")
        with progress.step("kg_clean", "Fusionando duplicados y normalizando nombres"):
            nodes = self._node_universe(staging)
            logger.info(
                f"Cleaning staging KG — {len(staging['entities'])} entity(ies), "
                f"{len(staging['relations'])} relation(s), {len(nodes)} node(s) in universe"
            )

            det_map, representatives = self._deterministic_merge(nodes)
            logger.info(f"Deterministic merge — {len(nodes)} → {len(representatives)} node(s)")
            progress.advance(
                0.3, f"{len(nodes)} → {len(representatives)} nodo(s) por fusión mecánica"
            )

            progress.checkpoint()
            canonical, drop = self._propose_alias_mapping(
                representatives, staging["relations"], det_map
            )
            progress.advance(0.85, f"{len(canonical)} alias propuesto(s), {len(drop)} descarte(s)")

            llm_map = self._llm_alias_map(canonical, set(representatives))
            node_map = self._compose_node_map(nodes, det_map, llm_map, drop)
            cleaned = self._apply_node_map(staging, node_map)

            logger.success(
                f"Cleaned — entities {len(staging['entities'])}→{len(cleaned['entities'])}, "
                f"relations {len(staging['relations'])}→{len(cleaned['relations'])}"
            )
        progress.advance(1.0)
        return cleaned

    # The node universe is entities plus every relation endpoint, so phrases that
    # only ever appear inside relations also get judged and can't stay dangling.
    @staticmethod
    def _node_universe(graph: dict) -> list[str]:
        nodes = set(graph["entities"])
        for source, _, target in graph["relations"]:
            nodes.add(source)
            nodes.add(target)
        return sorted(nodes)

    # Conservative key: casing, accents, an optional configurable qualifier and a
    # trailing plural suffix. No parenthesis stripping, to keep e.g. O(n) vs O(log n) apart.
    @staticmethod
    def _norm_key(name: str) -> str:
        s = name.lower().strip()
        if config.KG_BUILDER_MERGE_QUALIFIER_PATTERN:
            s = re.sub(config.KG_BUILDER_MERGE_QUALIFIER_PATTERN, "", s)
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"\s+", " ", s).strip()
        for suffix in config.KG_BUILDER_PLURAL_SUFFIXES:
            if len(s) > MIN_SINGULARIZE_LENGTH and s.endswith(suffix):
                return s[: -len(suffix)]
        return s

    # Merge only mechanical variants deterministically; the survivor is a
    # capitalized, short form when available.
    def _deterministic_merge(self, nodes: list[str]) -> tuple[dict, list[str]]:
        groups = defaultdict(list)
        for n in nodes:
            groups[self._norm_key(n)].append(n)
        variant_to_canon = {}
        representatives = []
        for members in groups.values():
            canon = min(members, key=lambda x: (x[:1].islower(), len(x)))
            representatives.append(canon)
            for m in members:
                variant_to_canon[m] = canon
        return variant_to_canon, sorted(representatives)

    # Each node is listed with its outgoing relations (remapped to representatives)
    # so the model can disambiguate short or ambiguous names.
    @staticmethod
    def _nodes_block(nodes: list[str], relations: list[list], det_map: dict) -> str:
        outgoing = defaultdict(list)
        for source, relation, target in relations:
            outgoing[det_map.get(source, source)].append(f"{relation} {det_map.get(target, target)}")
        lines = []
        for n in nodes:
            evidence = "; ".join(outgoing[n][: config.KG_MAX_EVIDENCE_RELATIONS])
            lines.append(f"- {n}" + (f"  [{evidence}]" if evidence else ""))
        return "\n".join(lines)

    def _propose_alias_mapping(
        self, nodes: list[str], relations: list[list], det_map: dict
    ) -> tuple[dict, set]:
        prompt = clean_graph_nodes_prompt(self._nodes_block(nodes, relations, det_map))
        response = inference.generate(
            model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=False
        ).response
        raw = self._parse_object(response, "[clean] ")
        if raw is None:
            logger.warning("Alias proposal unavailable — keeping the deterministic merge only")
            return {}, set()
        return raw.get("canonical", {}) or {}, set(raw.get("drop", []) or [])

    # Force every canonical to be an existing node (drops invented names).
    @staticmethod
    def _llm_alias_map(canonical: dict, valid: set) -> dict:
        alias_map = {}
        for canon, aliases in canonical.items():
            target = canon if canon in valid else next((a for a in aliases if a in valid), None)
            if target is None:
                continue
            for m in (canon, *aliases):
                if m in valid:
                    alias_map[m] = target
        return alias_map

    # Compose deterministic merge -> LLM merge -> drops into one node->canonical map;
    # a dropped node maps to None.
    @staticmethod
    def _compose_node_map(nodes: list[str], det_map: dict, llm_map: dict, drop: set) -> dict:
        node_map = {}
        for n in nodes:
            rep = det_map.get(n, n)
            node_map[n] = None if rep in drop else llm_map.get(rep, rep)
        return node_map

    @staticmethod
    def _apply_node_map(graph: dict, node_map: dict) -> dict:
        entities = sorted({c for c in node_map.values() if c})
        ents = set(entities)
        relations = set()
        for source, relation, target in graph["relations"]:
            canon_source, canon_target = node_map.get(source), node_map.get(target)
            # Keep a relation only when both remapped endpoints survive as entities.
            if canon_source in ents and canon_target in ents:
                relations.add((canon_source, relation, canon_target))
        return {
            "entities": entities,
            "edges": sorted({r[1] for r in relations}),
            "relations": sorted(list(r) for r in relations),
        }

    # CURATE --------------------------------------------------------------------------------------

    def curate(self, cleaned: dict, output_path: str | Path | None = None) -> dict:
        output_path = output_path or config.KG_AUTOGENERATED_PATH

        progress.phase("curate")
        with progress.step("kg_curate", "Agrupando en dominios y tipando las relaciones"):
            concepts = cleaned["entities"]
            relations = cleaned["relations"]
            logger.info(
                f"Curating — {len(concepts)} concept(s), {len(relations)} relation(s)"
            )

            progress.checkpoint()
            progress.advance(0.1, f"clasificando {len(concepts)} concepto(s) en dominios")
            concepts_by_domains, non_taggable = self._curate_domains(concepts, relations)
            logger.info(
                f"Domains — {len(concepts_by_domains)} domain(s), "
                f"{len(non_taggable)} non-taggable concept(s)"
            )
            progress.advance(0.8, f"{len(concepts_by_domains)} dominio(s)")

            universe = {c for cs in concepts_by_domains.values() for c in cs}
            typed = self._build_typed_relations(relations, universe)
            typed = self._break_cycles(typed)
            logger.info(f"Relations — {len(typed)} typed group(s) over {len(universe)} concept(s)")

            curated = {
                "concepts_by_domains": concepts_by_domains,
                "generic_non_taggable_concepts": non_taggable,
                "relations": typed,
            }
            _source_docs.save_json(curated, output_path)
            logger.success(
                f"Curated draft → {output_path} — "
                f"{len(universe)} concept(s), {len(typed)} typed relation group(s)"
            )
        progress.advance(1.0)
        return curated

    def _curate_domains(self, concepts: list[str], relations: list[list]) -> tuple[dict, list[str]]:
        prompt = curate_graph_domains_prompt(self._nodes_block(concepts, relations, {}))
        response = inference.generate(
            model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=False
        ).response
        raw = self._parse_object(response, "[domains] ") or {}
        return self._reconcile_domains(
            concepts, raw.get("domains", {}) or {}, raw.get("non_taggable", []) or []
        )

    @staticmethod
    def _reconcile_domains(
        concepts: list[str], domains_raw: dict, non_taggable_raw: list
    ) -> tuple[dict, list[str]]:
        valid = set(concepts)
        placed: set[str] = set()
        by_domain: dict[str, list[str]] = {}
        for domain, members in domains_raw.items():
            if not isinstance(members, list):
                continue
            kept = sorted({c for c in members if c in valid and c not in placed})
            if kept:
                placed.update(kept)
                by_domain[domain] = kept
        leftover = sorted(c for c in concepts if c not in placed)
        if leftover:
            by_domain.setdefault(config.KG_BUILDER_UNCLASSIFIED_DOMAIN, []).extend(leftover)
        non_taggable = sorted({c for c in non_taggable_raw if c in valid})
        return by_domain, non_taggable

    def _build_typed_relations(self, relations: list[list], universe: set) -> list[dict]:
        buckets = {relation.key: defaultdict(list) for relation in self.schema}
        for source, key, target in relations:
            if source not in universe or target not in universe:
                continue
            if key not in self.schema:
                key = self.schema.fallback
                if key is None:
                    continue
            if target not in buckets[key][source]:
                buckets[key][source].append(target)

        typed = []
        for relation in self.schema:
            data = buckets[relation.key]
            if not data:
                continue
            relations_data = {source: sorted(data[source]) for source in sorted(data)}
            typed.append({"details": relation.details(), "relations_data": relations_data})
        return typed

    @staticmethod
    def _break_cycles(typed: list[dict]) -> list[dict]:
        for group in typed:
            details = group["details"]
            if not (details.get("acyclic") and details.get("directed")):
                continue
            graph = nx.DiGraph()
            for source, targets in group["relations_data"].items():
                graph.add_edges_from((source, target) for target in targets)
            removed = []
            while not nx.is_directed_acyclic_graph(graph):
                source, target = nx.find_cycle(graph)[-1][:2]
                graph.remove_edge(source, target)
                removed.append((source, target))
            if not removed:
                continue
            rebuilt = defaultdict(list)
            for source, target in graph.edges():
                rebuilt[source].append(target)
            group["relations_data"] = {s: sorted(rebuilt[s]) for s in sorted(rebuilt)}
            logger.warning(
                f"Broke {len(removed)} back-edge(s) in acyclic '{details['verbose']}': {removed}"
            )
        return typed


def _parse_json_object(text: str) -> tuple[dict | None, str | None]:
    raw = repair_json(text, return_objects=True)
    if not isinstance(raw, dict):
        return None, "model did not return a JSON object"
    return raw, None
