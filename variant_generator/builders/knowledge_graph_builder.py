import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from json_repair import repair_json
from loguru import logger

from .. import config, inference, progress
from ..prompts import (
    assign_leftover_concepts_prompt,
    curate_graph_domains_prompt,
    extract_typed_graph_prompt,
    filter_graph_nodes_prompt,
    link_cross_domain_relations_prompt,
    link_domain_relations_prompt,
    merge_candidate_groups_prompt,
    review_taggable_concepts_prompt,
)
from ..relations import RelationSchema
from ..utils import parse_with_repair
from . import _source_docs

MIN_SINGULARIZE_LENGTH = 3

# Shares of a whole build, taken from a timed run rather than from how the code looks. The
# previous numbers guessed extraction at 48 % because it is the only per-chunk phase; it
# measured 8 %, while the handful of calls that reason over the whole inventory — linking,
# merging, taggability — are where the build actually spends its hour. Typing the relations
# is deterministic and takes milliseconds, so it only carries a weight to avoid a bar that
# jumps. Conversion keeps a real share for the first build and simply flies past on later
# ones, where the markdown cache answers instead of Docling.
BUILD_PHASES = (
    ("convert", "Convirtiendo los documentos del corpus", 11),
    ("extract", "Extrayendo conceptos y relaciones", 8),
    ("clean", "Fusionando duplicados y normalizando nombres", 25),
    ("domains", "Agrupando los conceptos en dominios", 9),
    ("link", "Enlazando conceptos y ordenando el temario", 26),
    ("curate", "Tipando las relaciones y rompiendo ciclos", 1),
    ("taggable", "Revisando qué conceptos sirven como etiqueta", 20),
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
                    config.EMBEDDING_LLM,
                )
            )
        )
        logger.info(f"Preparing knowledge graph model(s): {', '.join(models)}")
        failed = [m for m in models if not inference.ensure_model(m)]
        if failed:
            raise RuntimeError(f"Failed to install model(s): {', '.join(failed)}")
        for model in models:
            progress.checkpoint()
            inference.warmup(model, is_embedding=(model == config.EMBEDDING_LLM))
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

    # Linking is NOT done here any more: it used to run over the raw inventory, where the
    # same idea is still present under several names, and every relation whose endpoint was
    # later merged or dropped was thrown away by `_apply_node_map`. It now runs in `curate`,
    # once the names are canonical and the domains exist to break the question into pieces.
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
    ) -> list[tuple[str, list[tuple[str, str]]]]:
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

                chunks = _source_docs.chunk_markdown(text, self.chunk_size)
                if not chunks:
                    logger.warning(f"[{file_path.name}] produced no text")
                    continue
                documents.append((file_path.name, chunks))
                logger.info(f"[{idx}/{len(files)} {file_path.name}] {len(chunks)} chunk(s)")

        progress.advance(1.0, f"{len(documents)} documento(s) listos")
        return documents

    def _extract_documents(
        self, documents: list[tuple[str, list[tuple[str, str]]]]
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
                for ci, (location, chunk) in enumerate(chunks, 1):
                    progress.checkpoint()
                    done += 1
                    reporter.tick(
                        done,
                        detail=(
                            f"{name} · {location or f'fragmento {ci}'} · "
                            f"{len(concepts)} concepto(s), {len(relations)} relación(es)"
                        ),
                    )
                    progress.advance(
                        (done - 1) / total,
                        f"fragmento {done}/{total} · {len(concepts)} concepto(s)",
                    )
                    tag = f"[{name} · chunk {ci}/{len(chunks)}] "
                    chunk_concepts, chunk_relations = self._extract_from_chunk(
                        chunk, tag, location
                    )
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

    # The only per-chunk call of the build, so the only one that stays without reasoning:
    # every other model call here happens a handful of times and can afford to think.
    def _extract_from_chunk(
        self, chunk: str, log_prefix: str, location: str = ""
    ) -> tuple[list[str], list[list[str]]]:
        prompt = extract_typed_graph_prompt(chunk, self.schema, location)
        response = inference.generate(
            model=config.KG_BUILDER_EXTRACTION_MODEL, prompt=prompt, think=False
        ).response
        raw = self._parse_object(response, log_prefix)
        if raw is None:
            return [], []
        concepts = [c.strip() for c in raw.get("concepts", []) if isinstance(c, str) and c.strip()]
        relations = self._valid_relations(raw.get("relations", []), allowed=None)
        return concepts, relations

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
    #
    # It used to be ONE model call over the whole node universe, asked to emit a complete
    # partition in which every one of several hundred nodes appears exactly once — and it
    # had to answer two unrelated questions at the same time: which names are the same
    # concept, and which nodes are not concepts at all. The merges it missed are still
    # visible downstream, so the two questions are now asked separately, and each of them
    # in bites: merges only inside groups that name-similarity already flagged as
    # suspicious, drops in batches of nodes. Blocking first and escalating only what is
    # ambiguous is the same rule the rest of the pipeline follows.
    def clean(self, staging: dict) -> dict:
        progress.phase("clean")
        nodes = self._node_universe(staging)
        logger.info(
            f"Cleaning staging KG — {len(staging['entities'])} entity(ies), "
            f"{len(staging['relations'])} relation(s), {len(nodes)} node(s) in universe"
        )

        det_map, representatives = self._deterministic_merge(nodes)
        logger.info(f"Deterministic merge — {len(nodes)} → {len(representatives)} node(s)")
        progress.advance(0.1, f"{len(nodes)} → {len(representatives)} nodo(s) por fusión mecánica")

        llm_map = self._propose_merges(representatives, staging["relations"], det_map)
        canonicals = sorted({llm_map.get(n, n) for n in representatives})
        logger.info(f"Semantic merge — {len(representatives)} → {len(canonicals)} node(s)")
        progress.advance(0.6, f"{len(canonicals)} nodo(s) tras la fusión semántica")

        surviving = {n: llm_map.get(det_map.get(n, n), det_map.get(n, n)) for n in nodes}
        drop = self._propose_drops(canonicals, staging["relations"], surviving)
        progress.advance(0.95, f"{len(drop)} descarte(s)")

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

    @staticmethod
    def _outgoing(relations: list[list], node_map: dict) -> dict:
        outgoing = defaultdict(list)
        for source, relation, target in relations:
            outgoing[node_map.get(source, source)].append(
                f"{relation} {node_map.get(target, target)}"
            )
        return outgoing

    # Each node is listed with its outgoing relations (remapped to survivors)
    # so the model can disambiguate short or ambiguous names.
    @classmethod
    def _nodes_block(cls, nodes: list[str], relations: list[list], node_map: dict) -> str:
        outgoing = cls._outgoing(relations, node_map)
        lines = []
        for n in nodes:
            evidence = "; ".join(outgoing[n][: config.KG_MAX_EVIDENCE_RELATIONS])
            lines.append(f"- {n}" + (f"  [{evidence}]" if evidence else ""))
        return "\n".join(lines)

    @classmethod
    def _groups_block(cls, groups: list[list[str]], relations: list[list], node_map: dict) -> str:
        outgoing = cls._outgoing(relations, node_map)
        lines = []
        for idx, group in enumerate(groups, 1):
            lines.append(f"## Grupo {idx}")
            for name in group:
                evidence = "; ".join(outgoing[name][: config.KG_MAX_EVIDENCE_RELATIONS])
                lines.append(f"- {name}" + (f"  [{evidence}]" if evidence else ""))
        return "\n".join(lines)

    # MERGE ---------------------------------------------------------------------------------------

    def _propose_merges(self, nodes: list[str], relations: list[list], det_map: dict) -> dict:
        groups = self._merge_candidates(nodes)
        if not groups:
            logger.info("No merge candidates found — keeping the deterministic merge only")
            return {}

        per_call = config.KG_BUILDER_MERGE_GROUPS_PER_CALL
        batches = [groups[i : i + per_call] for i in range(0, len(groups), per_call)]
        logger.info(
            f"{len(groups)} merge candidate group(s) covering "
            f"{sum(len(g) for g in groups)} name(s), in {len(batches)} call(s)"
        )

        valid = set(nodes)
        alias_map: dict[str, str] = {}
        with progress.step(
            "kg_merge", "Decidiendo qué nombres son el mismo concepto", len(batches)
        ) as reporter:
            for idx, batch in enumerate(batches, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=f"{len(batch)} grupo(s)")
                progress.advance(
                    0.1 + 0.4 * (idx - 1) / len(batches), f"grupos {idx}/{len(batches)}"
                )
                prompt = merge_candidate_groups_prompt(
                    self._groups_block(batch, relations, det_map)
                )
                response = inference.generate(
                    model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=True
                ).response
                raw = self._parse_object(response, f"[merge {idx}/{len(batches)}] ")
                if raw is None:
                    continue
                alias_map.update(self._merge_alias_map(raw.get("merges", []), valid))

        return self._resolve_chains(alias_map)

    # Candidate groups come from the names' own embeddings: a suspicion cheap enough to
    # compute for the whole inventory, which is what lets the model be asked about five
    # names instead of six hundred. Note this embeds NAMES, which retrieval deliberately
    # never does — here they are not the answer, only the shortlist the model then judges.
    def _merge_candidates(self, nodes: list[str]) -> list[list[str]]:
        if len(nodes) < 2:
            return []
        vectors = self._embed_names(nodes)
        if vectors is None:
            return []

        similarity = vectors @ vectors.T
        np.fill_diagonal(similarity, 0.0)
        components = self._components(
            list(range(len(nodes))), similarity, config.KG_BUILDER_MERGE_SIMILARITY
        )
        return [
            sorted(nodes[i] for i in members) for members in components if len(members) > 1
        ]

    # Connected components chain (A~B, B~C keeps C even when A and C are unrelated), so a
    # component that grows past the cap is re-cut at a stricter threshold instead of being
    # handed over as one unanswerable group.
    def _components(self, index: list[int], similarity, threshold: float) -> list[list[int]]:
        parent = {i: i for i in index}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for position, a in enumerate(index):
            for b in index[position + 1 :]:
                if similarity[a, b] >= threshold:
                    parent[find(a)] = find(b)

        grouped = defaultdict(list)
        for i in index:
            grouped[find(i)].append(i)

        out = []
        for members in grouped.values():
            if len(members) <= config.KG_BUILDER_MAX_MERGE_GROUP or threshold >= 0.95:
                out.append(members)
            else:
                out.extend(self._components(members, similarity, threshold + 0.05))
        return out

    @staticmethod
    def _embed_names(names: list[str]):
        try:
            vectors = []
            for start in range(0, len(names), config.EMBEDDING_BATCH_SIZE):
                progress.checkpoint()
                batch = names[start : start + config.EMBEDDING_BATCH_SIZE]
                vectors.extend(inference.embed_batch(model=config.EMBEDDING_LLM, texts=batch))
        except progress.Cancelled:
            raise
        except Exception as e:
            logger.warning(f"Could not embed node names ({e}) — skipping the semantic merge")
            return None

        matrix = np.array(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)

    # Force every canonical to be an existing node (drops invented names).
    @staticmethod
    def _merge_alias_map(merges: list, valid: set) -> dict:
        alias_map = {}
        for merge in merges or []:
            if not isinstance(merge, dict):
                continue
            canonical = merge.get("canonical")
            aliases = [a for a in (merge.get("aliases") or []) if isinstance(a, str)]
            if not isinstance(canonical, str):
                continue
            target = canonical if canonical in valid else next((a for a in aliases if a in valid), None)
            if target is None:
                continue
            for name in (canonical, *aliases):
                if name in valid and name != target:
                    alias_map[name] = target
        return alias_map

    # A group judged in one call can still come back as A→B and B→C; nothing may end up
    # pointing at a name that is itself an alias.
    @staticmethod
    def _resolve_chains(alias_map: dict) -> dict:
        resolved = {}
        for name in alias_map:
            target = alias_map[name]
            seen = {name}
            while target in alias_map and target not in seen:
                seen.add(target)
                target = alias_map[target]
            if target != name:
                resolved[name] = target
        return resolved

    # DROP ----------------------------------------------------------------------------------------

    def _propose_drops(self, nodes: list[str], relations: list[list], node_map: dict) -> set:
        size = config.KG_BUILDER_CLEAN_BATCH_SIZE
        batches = [nodes[i : i + size] for i in range(0, len(nodes), size)]
        drop: set[str] = set()

        with progress.step(
            "kg_drop", "Descartando lo que no nombra un concepto", len(batches)
        ) as reporter:
            for idx, batch in enumerate(batches, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=f"{len(batch)} nodo(s)")
                progress.advance(
                    0.6 + 0.35 * (idx - 1) / len(batches), f"lote {idx}/{len(batches)}"
                )
                prompt = filter_graph_nodes_prompt(self._nodes_block(batch, relations, node_map))
                # Reasoning stays ON, and this is measured, not assumed: it looks like a
                # lexical verdict that could be read off the name, and turning it off is 6.8x
                # faster — but over the same 180 already-clean nodes it went from 1 drop to
                # 20, taking `Cohesión`, `El método de la Burbuja`, `Else` and `Error de
                # compilación` with it. The deliberation is what keeps this pass timid, and a
                # concept dropped here is gone from the graph for good.
                response = inference.generate(
                    model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=True
                ).response
                raw = self._parse_object(response, f"[drop {idx}/{len(batches)}] ")
                if raw is None:
                    continue

                verdicts = raw.get("drop") or {}
                if isinstance(verdicts, list):
                    verdicts = {n: "" for n in verdicts if isinstance(n, str)}
                if not isinstance(verdicts, dict):
                    continue
                valid = set(batch)
                for name, reason in verdicts.items():
                    if name in valid:
                        drop.add(name)
                        logger.info(f"drop '{name}': {reason}")

        logger.info(f"Node filter — {len(drop)} node(s) dropped of {len(nodes)}")
        return drop

    # Compose deterministic merge -> semantic merge -> drops into one node->canonical map;
    # a node whose canonical was dropped maps to None.
    @staticmethod
    def _compose_node_map(nodes: list[str], det_map: dict, llm_map: dict, drop: set) -> dict:
        node_map = {}
        for n in nodes:
            representative = det_map.get(n, n)
            canonical = llm_map.get(representative, representative)
            node_map[n] = None if canonical in drop else canonical
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
        concepts = cleaned["entities"]
        relations = cleaned["relations"]
        logger.info(f"Curating — {len(concepts)} concept(s), {len(relations)} relation(s)")

        progress.phase("domains", f"clasificando {len(concepts)} concepto(s)")
        with progress.step("kg_domains", "Agrupando los conceptos en dominios"):
            progress.checkpoint()
            concepts_by_domains = self._curate_domains(concepts, relations)
            logger.info(f"Domains — {len(concepts_by_domains)} domain(s)")
        progress.advance(1.0, f"{len(concepts_by_domains)} dominio(s)")

        relations = self._link_relations(concepts_by_domains, relations)

        progress.phase("curate")
        with progress.step("kg_curate", "Tipando las relaciones y rompiendo ciclos"):
            universe = {c for cs in concepts_by_domains.values() for c in cs}
            typed = self._break_cycles(self._build_typed_relations(relations, universe))
            logger.info(f"Relations — {len(typed)} typed group(s) over {len(universe)} concept(s)")
        progress.advance(1.0)

        non_taggable = self._review_taggability(concepts_by_domains, relations)

        curated = {
            "concepts_by_domains": concepts_by_domains,
            "generic_non_taggable_concepts": non_taggable,
            "relations": typed,
        }
        _source_docs.save_json(curated, output_path)
        logger.success(
            f"Curated draft → {output_path} — {len(universe)} concept(s), "
            f"{len(universe) - len(non_taggable)} taggable, "
            f"{len(typed)} typed relation group(s)"
        )
        return curated

    def _curate_domains(self, concepts: list[str], relations: list[list]) -> dict:
        prompt = curate_graph_domains_prompt(self._nodes_block(concepts, relations, {}))
        response = inference.generate(
            model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=True
        ).response
        raw = self._parse_object(response, "[domains] ") or {}
        by_domain = self._reconcile_domains(concepts, raw.get("domains", {}) or {})
        return self._place_leftovers(by_domain, relations)

    # A concept parked in the unclassified bucket is not a concept the model judged hard to
    # place — it is one it never reached. It keeps its relations, so it still works as
    # scaffolding, but it gets no domain-level review: neither the per-domain linking nor
    # the taggability pass can reason about a bucket that shares no theme. Asking again,
    # with only the leftovers and the domains already fixed, is a much smaller question.
    def _place_leftovers(self, by_domain: dict, relations: list[list]) -> dict:
        unclassified = config.KG_BUILDER_UNCLASSIFIED_DOMAIN
        leftovers = by_domain.get(unclassified)
        if not leftovers:
            return by_domain

        placed = {d: list(m) for d, m in by_domain.items() if d != unclassified}
        if not placed:
            return by_domain

        logger.info(f"Placing {len(leftovers)} leftover concept(s) into {len(placed)} domain(s)")
        remaining = list(leftovers)
        # Small batches and repeated rounds, because the failure being repaired here is
        # "forgot to answer", not "could not decide": at 60 names a call the model placed 24
        # of 84, and the ones it skipped are not the hard ones — asked again, in a shorter
        # list, most of them get placed. Rounds stop as soon as one adds nothing, so a
        # genuinely unplaceable concept costs one extra call and not three.
        for _ in range(config.KG_BUILDER_DOMAIN_ROUNDS):
            before = len(remaining)
            remaining = self._assign_round(remaining, placed, relations)
            if not remaining or len(remaining) == before:
                break

        for domain in placed:
            placed[domain] = sorted(set(placed[domain]))
        if remaining:
            placed[unclassified] = sorted(remaining)
        logger.info(
            f"Leftovers — {len(leftovers) - len(remaining)} placed, {len(remaining)} still unclassified"
        )
        return placed

    def _assign_round(self, pending: list[str], placed: dict, relations: list[list]) -> list[str]:
        size = config.KG_BUILDER_DOMAIN_BATCH_SIZE
        batches = [pending[i : i + size] for i in range(0, len(pending), size)]
        unplaced = set(pending)

        for idx, batch in enumerate(batches, 1):
            progress.checkpoint()
            progress.advance(
                0.5 + 0.45 * (idx - 1) / len(batches), f"sin dominio: {len(unplaced)} concepto(s)"
            )
            prompt = assign_leftover_concepts_prompt(
                self._domains_block(placed), self._nodes_block(batch, relations, {})
            )
            response = inference.generate(
                model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=False
            ).response
            raw = self._parse_object(response, f"[domains · leftovers {idx}/{len(batches)}] ") or {}
            for domain, members in (raw.get("domains") or {}).items():
                if domain not in placed or not isinstance(members, list):
                    continue
                for concept in members:
                    if concept in unplaced:
                        placed[domain].append(concept)
                        unplaced.discard(concept)

        return [c for c in pending if c in unplaced]

    # LINKING -------------------------------------------------------------------------------------

    # One question over the whole inventory produced 10 prerequisite edges for 199 concepts:
    # ordering a syllabus is not something a model does in one turn over a flat list. Asked
    # per domain — a dozen concepts at a time, with the relations already known as evidence —
    # and then once for what crosses domains, it is a question that can actually be answered.
    def _link_relations(self, concepts_by_domains: dict, relations: list[list]) -> list[list]:
        domains = list(concepts_by_domains)
        if not domains:
            return relations

        progress.phase("link", f"{len(domains)} dominio(s)")
        known = {tuple(r) for r in relations}
        before = len(known)
        total = len(domains) + 1

        with progress.step(
            "kg_link", "Enlazando conceptos y ordenando el temario", total
        ) as reporter:
            for idx, domain in enumerate(domains, 1):
                progress.checkpoint()
                members = concepts_by_domains[domain]
                reporter.tick(idx, detail=f"{domain} · {len(members)} concepto(s)")
                progress.advance((idx - 1) / total, f"{domain} ({idx}/{len(domains)})")
                known.update(
                    tuple(r) for r in self._link_domain(domain, members, relations)
                )

            progress.checkpoint()
            reporter.tick(total, detail="relaciones entre dominios")
            progress.advance((total - 1) / total, "relaciones entre dominios")
            known.update(tuple(r) for r in self._link_cross_domain(concepts_by_domains))

        logger.info(f"Linking added {len(known) - before} relation(s)")
        progress.advance(1.0, f"{len(known) - before} relación(es) nuevas")
        return sorted(list(r) for r in known)

    def _link_domain(self, domain: str, members: list[str], relations: list[list]) -> list[list]:
        if len(members) < 2:
            return []
        prompt = link_domain_relations_prompt(
            domain, self._nodes_block(members, relations, {}), self.schema
        )
        response = inference.generate(
            model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=True
        ).response
        raw = self._parse_object(response, f"[link · {domain}] ")
        if raw is None:
            return []
        return self._valid_relations(raw.get("relations", []), allowed=set(members))

    def _link_cross_domain(self, concepts_by_domains: dict) -> list[list]:
        if len(concepts_by_domains) < 2:
            return []
        prompt = link_cross_domain_relations_prompt(
            self._domains_block(concepts_by_domains), self.schema
        )
        response = inference.generate(
            model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=True
        ).response
        raw = self._parse_object(response, "[link · global] ")
        if raw is None:
            return []

        domain_of = {c: d for d, members in concepts_by_domains.items() for c in members}
        proposed = self._valid_relations(raw.get("relations", []), allowed=set(domain_of))
        crossing = [r for r in proposed if domain_of[r[0]] != domain_of[r[2]]]
        if len(crossing) < len(proposed):
            logger.info(
                f"Cross-domain pass — dropped {len(proposed) - len(crossing)} relation(s) "
                f"that stayed inside one domain"
            )
        return crossing

    @staticmethod
    def _domains_block(concepts_by_domains: dict) -> str:
        return "\n\n".join(
            f"## {domain}\n" + "\n".join(f"- {c}" for c in members)
            for domain, members in concepts_by_domains.items()
        )

    @staticmethod
    def _reconcile_domains(concepts: list[str], domains_raw: dict) -> dict:
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
        return by_domain

    # TAGGABILITY ---------------------------------------------------------------------------------

    # Domain assignment and taggability are two different judgements, and asking for both
    # in the same call gave the second one whatever attention was left after partitioning
    # a few hundred concepts: the draft came back with a handful of non-taggables and a
    # long tail of terms ("Codificación", "Diseño", "Ejecución") that label everything and
    # therefore identify nothing. One call per domain, judging only that, is the fix.
    def _review_taggability(self, concepts_by_domains: dict, relations: list[list]) -> list[str]:
        domains = list(concepts_by_domains)
        if not domains:
            return []

        progress.phase("taggable")
        non_taggable: set[str] = set()
        with progress.step(
            "kg_taggability", "Revisando qué conceptos sirven como etiqueta", len(domains)
        ) as reporter:
            for idx, domain in enumerate(domains, 1):
                progress.checkpoint()
                members = concepts_by_domains[domain]
                reporter.tick(idx, detail=f"{domain} · {len(members)} concepto(s)")
                progress.advance(
                    (idx - 1) / len(domains), f"{domain} ({idx}/{len(domains)})"
                )
                non_taggable.update(self._judge_domain(domain, members, domains, relations))

        logger.info(
            f"Taggability — {len(non_taggable)} concept(s) excluded from labelling "
            f"across {len(domains)} domain(s)"
        )
        progress.advance(1.0, f"{len(non_taggable)} concepto(s) no etiquetables")
        return sorted(non_taggable)

    def _judge_domain(
        self, domain: str, members: list[str], domains: list[str], relations: list[list]
    ) -> list[str]:
        prompt = review_taggable_concepts_prompt(
            domain,
            self._concepts_block(domains),
            self._nodes_block(members, relations, {}),
        )
        response = inference.generate(
            model=config.KG_BUILDER_CURATION_MODEL, prompt=prompt, think=True
        ).response
        raw = self._parse_object(response, f"[taggable · {domain}] ") or {}
        verdicts = raw.get("non_taggable") or {}
        if isinstance(verdicts, list):
            verdicts = {c: "" for c in verdicts if isinstance(c, str)}
        if not isinstance(verdicts, dict):
            return []

        valid = set(members)
        excluded = []
        for concept, reason in verdicts.items():
            if concept in valid:
                excluded.append(concept)
                logger.info(f"[{domain}] non-taggable '{concept}': {reason}")
        return excluded

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
