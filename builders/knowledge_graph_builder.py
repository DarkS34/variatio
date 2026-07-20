import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import dspy
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
from dspy.utils.callback import BaseCallback
from json_repair import repair_json
from kg_gen import KGGen
from kg_gen.utils.chunk_text import chunk_text
from loguru import logger

from system import config, inference
from system.prompts import (
    clean_graph_nodes_prompt,
    curate_graph_domains_prompt,
    type_graph_relations_prompt,
)

from . import _source_docs


class _LMProgressCallback(BaseCallback):
    def __init__(self):
        self._done = 0
        self._total = 0
        self._last_bucket = -1

    # The builder sets the expected number of LM calls before extraction starts.
    def start(self, total: int):
        self._done = 0
        self._total = total
        self._last_bucket = -1

    def on_lm_end(self, call_id, outputs, exception=None):
        if not self._total:
            return
        self._done += 1
        pct = min(100, self._done * 100 // self._total)
        # Report in 10% steps only, so it shows progress instead of per-call noise.
        if pct // 10 > self._last_bucket:
            self._last_bucket = pct // 10
            logger.info(f"Building knowledge graph… {pct}%")


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

        self._progress = _LMProgressCallback()
        if verbose:
            dspy.settings.configure(callbacks=[self._progress])

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

        self._kg = KGGen(
            model=f"ollama_chat/{model}",
            api_base=config.OLLAMA_HOST,
            api_key="ollama",
            temperature=0.0,
        )
        self.chunk_size = config.KG_BUILDER_CHUNK_SIZE

    def build(
        self,
        input_dir: str,
        output_file_path: str,
        cluster: bool = False,
    ) -> dict:
        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"No supported files found in: {input_dir}")
            return {}

        logger.info(f"Found {len(files)} file(s) - extracting knowledge graph")

        # Read every file up front so the total call count for progress is known.
        texts: dict[Path, str] = {}
        for file_path in files:
            try:
                texts[file_path] = _source_docs.to_markdown(self._docling, file_path)
            except Exception as e:
                logger.exception(f"[{file_path.name}] skipped: {e}")
        if not texts:
            logger.error("No text extracted from any file")
            return {}

        # 2 LM calls per chunk (entities + relations); used to report % progress.
        total_calls = 2 * sum(len(chunk_text(t, self.chunk_size)) for t in texts.values())
        self._progress.start(total_calls)

        graphs = []
        for idx, (file_path, text) in enumerate(texts.items(), 1):
            tag = f"[{idx}/{len(texts)} {file_path.name}]"
            logger.info(f"{tag} extracting from text ({len(text):,} chars)")
            try:
                graph = self._kg.generate(
                    input_data=text,
                    chunk_size=self.chunk_size,
                    cluster=cluster,
                )
            except Exception as e:
                logger.exception(f"{tag} skipped: {e}")
                continue
            graphs.append(graph)
            logger.success(
                f"{tag} {len(graph.entities)} entity(ies), {len(graph.relations)} relation(s)"
            )

        if not graphs:
            logger.error("No graph produced from any file")
            return {}

        merged = graphs[0] if len(graphs) == 1 else self._kg.aggregate(graphs)
        staging = self._to_dict(merged)
        _source_docs.save_json(staging, output_file_path)
        logger.success(
            f"Staging KG written — {len(staging['entities'])} entity(ies), "
            f"{len(staging['relations'])} relation(s) → {output_file_path}"
        )
        return staging

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
        typed = self._type_relations(graph["edges"], relations, universe)
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

    # HELPERS -------------------------------------------------------------------------------------

    # Sets/tuplas → listas ordenadas: JSON-serializable y con diffs estables para la curación manual.
    @staticmethod
    def _to_dict(graph) -> dict:
        out = {
            "entities": sorted(graph.entities),
            "edges": sorted(graph.edges),
            "relations": sorted(list(r) for r in graph.relations),
        }
        if graph.entity_clusters:
            out["entity_clusters"] = {k: sorted(v) for k, v in graph.entity_clusters.items()}
        if graph.edge_clusters:
            out["edge_clusters"] = {k: sorted(v) for k, v in graph.edge_clusters.items()}
        return out

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