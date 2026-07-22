import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import networkx as nx
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
from json_repair import repair_json
from loguru import logger

from system import config, inference
from system.prompts import (
    clean_graph_nodes_prompt,
    curate_graph_domains_prompt,
    extract_typed_graph_prompt,
    link_global_relations_prompt,
    type_graph_relations_prompt,
)
from system.utils import parse_with_repair

from . import _source_docs


class KnowledgeGraphBuilder:
    RELATION_TYPES = {
        "prerrequisito": {
            "verbose": "tiene como prerrequisito",
            "directed": True,
            "acyclic": True,
            "use_in_embedding": False,
        },
        "es_un": {
            "verbose": "es un tipo de",
            "directed": True,
            "acyclic": False,
            "use_in_embedding": True,
        },
        "parte_de": {
            "verbose": "es parte de",
            "directed": True,
            "acyclic": False,
            "use_in_embedding": True,
        },
        "relacionado": {
            "verbose": "se relaciona con",
            "directed": False,
            "acyclic": False,
            "use_in_embedding": True,
        },
    }

    def __init__(self, model: str = config.KG_BUILDER_LLM, verbose: bool = True):
        logger.enable(__name__) if verbose else logger.disable(__name__)

        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = False
        pdf_options.do_table_structure = False

        self._docling = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pdf_options,
                    backend=PyPdfiumDocumentBackend,
                )
            },
        )

        self.model = model
        self.chunk_size = config.KG_BUILDER_CHUNK_SIZE
        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES

    def build(self, input_dir: str, output_file_path: str) -> dict:
        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"No supported files found in: {input_dir}")
            return {}

        logger.info(f"Found {len(files)} file(s) - extracting knowledge graph")

        concepts: set[str] = set()
        relations: set[tuple[str, str, str]] = set()
        for idx, file_path in enumerate(files, 1):
            try:
                text = _source_docs.to_markdown(self._docling, file_path)
            except Exception as e:
                logger.exception(f"[{file_path.name}] skipped: {e}")
                continue
            chunks = _source_docs.chunk_text(text, self.chunk_size)
            logger.info(f"[{idx}/{len(files)} {file_path.name}] {len(chunks)} chunk(s)")
            for ci, chunk in enumerate(chunks, 1):
                tag = f"[{idx}/{len(files)} {file_path.name} · chunk {ci}/{len(chunks)}] "
                chunk_concepts, chunk_relations = self._extract_from_chunk(chunk, tag)
                concepts.update(chunk_concepts)
                relations.update(tuple(r) for r in chunk_relations)

        if not concepts:
            logger.error("No concepts extracted from any file")
            return {}

        for src, _, tgt in relations:
            concepts.update((src, tgt))

        before = len(relations)
        relations.update(tuple(r) for r in self._link_global(sorted(concepts)))
        logger.info(f"Global linking pass added {len(relations) - before} relation(s)")

        staging = self._assemble(concepts, relations)
        _source_docs.save_json(staging, output_file_path)
        logger.success(
            f"Staging KG written — {len(staging['entities'])} entity(ies), "
            f"{len(staging['relations'])} relation(s) → {output_file_path}"
        )
        return staging

    # EXTRACTION ----------------------------------------------------------------------------------

    def _extract_from_chunk(self, chunk: str, log_prefix: str) -> tuple[list[str], list[list[str]]]:
        prompt = extract_typed_graph_prompt(chunk)
        response = inference.generate(model=self.model, think=False, prompt=prompt).response
        raw = self._parse_graph_object(response, log_prefix)
        if raw is None:
            return [], []
        concepts = [c.strip() for c in raw.get("concepts", []) if isinstance(c, str) and c.strip()]
        relations = self._valid_relations(raw.get("relations", []), allowed=None)
        return concepts, relations

    def _link_global(self, inventory: list[str]) -> list[list[str]]:
        if len(inventory) < 2:
            return []
        prompt = link_global_relations_prompt(self._concepts_block(inventory))
        response = inference.generate(model=self.model, think=False, prompt=prompt).response
        raw = self._parse_graph_object(response, "[global] ")
        if raw is None:
            return []
        return self._valid_relations(raw.get("relations", []), allowed=set(inventory))

    def _parse_graph_object(self, response: str, log_prefix: str) -> dict | None:
        def parse(text: str) -> tuple[dict | None, str | None]:
            raw = repair_json(text, return_objects=True)
            if not isinstance(raw, dict):
                return None, "model did not return a JSON object"
            return raw, None

        result, error = parse_with_repair(
            response,
            parse,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
            log_prefix=log_prefix,
        )
        if result is None:
            logger.warning(f"{log_prefix}unrecoverable JSON: {error}")
        return result

    @classmethod
    def _valid_relations(cls, raw: list, allowed: set[str] | None) -> list[list[str]]:
        out = []
        for triple in raw or []:
            if not (isinstance(triple, list) and len(triple) == 3):
                continue
            if not all(isinstance(x, str) for x in triple):
                continue
            src, rel, tgt = (x.strip() for x in triple)
            if not (src and tgt) or src == tgt or rel not in cls.RELATION_TYPES:
                continue
            if allowed is not None and (src not in allowed or tgt not in allowed):
                continue
            out.append([src, rel, tgt])
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

    # clean proposes a deduplicated, denoised graph for manual review; it never
    # touches the curated knowledge_graph.json.
    def clean(
        self,
        staging_path: str = config.KG_STAGING_PATH,
        output_path: str = config.KG_CLEANED_PATH,
    ) -> dict:
        graph = json.loads(Path(staging_path).read_text(encoding="utf-8"))
        nodes = self._node_universe(graph)
        logger.info(
            f"Loaded staging KG — {len(graph['entities'])} entity(ies), "
            f"{len(graph['relations'])} relation(s), {len(nodes)} node(s) in universe"
        )

        det_map, representatives = self._deterministic_merge(nodes)
        logger.info(f"Deterministic merge — {len(nodes)} → {len(representatives)} node(s)")

        canonical, drop = self._propose_alias_mapping(representatives, graph["relations"], det_map)
        llm_map = self._llm_alias_map(canonical, set(representatives))
        node_map = self._compose_node_map(nodes, det_map, llm_map, drop)
        cleaned = self._apply_node_map(graph, node_map)

        _source_docs.save_json(cleaned, output_path)
        logger.success(
            f"Cleaned proposal → {output_path} — "
            f"entities {len(graph['entities'])}→{len(cleaned['entities'])}, "
            f"relations {len(graph['relations'])}→{len(cleaned['relations'])}"
        )
        return cleaned

    def curate(
        self,
        cleaned_path: str = config.KG_CLEANED_PATH,
        output_path: str = config.KG_AUTOGENERATED_PATH,
    ) -> dict:
        graph = json.loads(Path(cleaned_path).read_text(encoding="utf-8"))
        concepts = graph["entities"]
        relations = graph["relations"]
        logger.info(
            f"Loaded cleaned KG — {len(concepts)} concept(s), {len(relations)} relation(s)"
        )

        concepts_by_domains, non_taggable = self._curate_domains(concepts, relations)
        logger.info(
            f"Domains — {len(concepts_by_domains)} domain(s), "
            f"{len(non_taggable)} non-taggable concept(s)"
        )

        universe = {c for cs in concepts_by_domains.values() for c in cs}
        identity = {key: key for key in self.RELATION_TYPES}
        typed = self._build_typed_relations(identity, relations, universe)
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
        return curated

    # CLEANUP -------------------------------------------------------------------------------------

    # The node universe is entities plus every relation endpoint, so phrases that
    # only ever appear inside relations also get judged and can't stay dangling.
    @staticmethod
    def _node_universe(graph: dict) -> list[str]:
        nodes = set(graph["entities"])
        for s, _, t in graph["relations"]:
            nodes.add(s)
            nodes.add(t)
        return sorted(nodes)

    # Conservative key: case, accents, "en X" qualifier and a trailing plural "s".
    # No parenthesis stripping, to keep e.g. O(n) vs O(log n) apart.
    @staticmethod
    def _norm_key(name: str) -> str:
        s = name.lower().strip()
        s = re.sub(r"\s+en (python|java)\b", "", s)
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) > 3 and s.endswith("s"):
            s = s[:-1]
        return s

    # Merge only mechanical variants deterministically; the survivor is a
    # capitalized, short form when available.
    @classmethod
    def _deterministic_merge(cls, nodes: list[str]) -> tuple[dict, list[str]]:
        groups = defaultdict(list)
        for n in nodes:
            groups[cls._norm_key(n)].append(n)
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
        for s, rel, t in relations:
            outgoing[det_map.get(s, s)].append(f"{rel} {det_map.get(t, t)}")
        lines = []
        for n in nodes:
            evidence = "; ".join(outgoing[n][:6])
            lines.append(f"- {n}" + (f"  [{evidence}]" if evidence else ""))
        return "\n".join(lines)

    def _propose_alias_mapping(self, nodes: list[str], relations: list[list], det_map: dict) -> tuple[dict, set]:
        prompt = clean_graph_nodes_prompt(self._nodes_block(nodes, relations, det_map))
        response = inference.generate(model=config.KG_CLEANUP_LLM, think=False, prompt=prompt).response
        raw = repair_json(response, return_objects=True)
        if not isinstance(raw, dict):
            raise ValueError("model did not return a JSON object")
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
        for s, rel, t in graph["relations"]:
            cs, ct = node_map.get(s), node_map.get(t)
            # Keep a relation only when both remapped endpoints survive as entities.
            if cs in ents and ct in ents:
                relations.add((cs, rel, ct))
        return {
            "entities": entities,
            "edges": sorted({r[1] for r in relations}),
            "relations": sorted(list(r) for r in relations),
        }

    # CURATE --------------------------------------------------------------------------------------

    def _curate_domains(self, concepts: list[str], relations: list[list]) -> tuple[dict, list[str]]:
        prompt = curate_graph_domains_prompt(self._nodes_block(concepts, relations, {}))
        response = inference.generate(model=config.KG_CLEANUP_LLM, think=False, prompt=prompt).response
        raw = repair_json(response, return_objects=True)
        if not isinstance(raw, dict):
            raise ValueError("model did not return a JSON object")
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
            by_domain.setdefault("Sin clasificar", []).extend(leftover)
        non_taggable = sorted({c for c in non_taggable_raw if c in valid})
        return by_domain, non_taggable

    def _type_relations(self, edges: list[str], relations: list[list], universe: set) -> list[dict]:
        prompt = type_graph_relations_prompt(self._edges_block(edges, relations))
        response = inference.generate(model=config.KG_CLEANUP_LLM, think=False, prompt=prompt).response
        raw = repair_json(response, return_objects=True)
        mapping = raw if isinstance(raw, dict) else {}
        return self._build_typed_relations(mapping, relations, universe)

    @staticmethod
    def _edges_block(edges: list[str], relations: list[list]) -> str:
        example: dict[str, tuple[str, str]] = {}
        for s, verb, t in relations:
            example.setdefault(verb, (s, t))
        lines = []
        for verb in sorted(edges):
            ex = example.get(verb)
            hint = f"  (p.ej. {ex[0]} → {ex[1]})" if ex else ""
            lines.append(f'- "{verb}"{hint}')
        return "\n".join(lines)

    @classmethod
    def _build_typed_relations(cls, mapping: dict, relations: list[list], universe: set) -> list[dict]:
        buckets = {k: defaultdict(list) for k in cls.RELATION_TYPES}
        for s, verb, t in relations:
            if s not in universe or t not in universe:
                continue
            key = mapping.get(verb)
            if key not in cls.RELATION_TYPES:
                key = "relacionado"
            if t not in buckets[key][s]:
                buckets[key][s].append(t)
        typed = []
        for key, details in cls.RELATION_TYPES.items():
            data = buckets[key]
            if not data:
                continue
            relations_data = {s: sorted(data[s]) for s in sorted(data)}
            typed.append({"details": dict(details), "relations_data": relations_data})
        return typed

    @staticmethod
    def _break_cycles(typed: list[dict]) -> list[dict]:
        for group in typed:
            details = group["details"]
            if not (details.get("acyclic") and details.get("directed")):
                continue
            graph = nx.DiGraph()
            for src, targets in group["relations_data"].items():
                graph.add_edges_from((src, tgt) for tgt in targets)
            removed = []
            while not nx.is_directed_acyclic_graph(graph):
                src, tgt = nx.find_cycle(graph)[-1][:2]
                graph.remove_edge(src, tgt)
                removed.append((src, tgt))
            if not removed:
                continue
            rebuilt = defaultdict(list)
            for src, tgt in graph.edges():
                rebuilt[src].append(tgt)
            group["relations_data"] = {s: sorted(rebuilt[s]) for s in sorted(rebuilt)}
            logger.warning(
                f"Broke {len(removed)} back-edge(s) in acyclic '{details['verbose']}': {removed}"
            )
        return typed