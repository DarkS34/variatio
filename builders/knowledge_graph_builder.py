import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import dspy
import ollama
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
from dspy.utils.callback import BaseCallback
from json_repair import repair_json
from kg_gen import KGGen
from kg_gen.utils.chunk_text import chunk_text
from loguru import logger

from system import config
from system.prompts import clean_graph_nodes_prompt


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
    SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")

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
        input_path = Path(input_dir)
        files = sorted(
            p
            for p in input_path.iterdir()
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS
        )
        if not files:
            logger.error(f"No supported files found in: {input_dir}")
            return {}

        logger.info(f"Found {len(files)} file(s) - extracting knowledge graph")

        # Read every file up front so the total call count for progress is known.
        texts: dict[Path, str] = {}
        for file_path in files:
            try:
                texts[file_path] = self._to_text(file_path)
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
        self._save(staging, output_file_path)
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
        output_path: str = config.KG_STAGING_CLEANED_PATH,
    ) -> dict:
        graph = json.loads(Path(staging_path).read_text(encoding="utf-8"))
        nodes = self._node_universe(graph)
        logger.info(
            f"Loaded staging KG — {len(graph['entities'])} entity(ies), "
            f"{len(graph['relations'])} relation(s), {len(nodes)} node(s) in universe"
        )

        det_map, representatives = self._deterministic_merge(nodes)
        logger.info(f"Deterministic merge — {len(nodes)} → {len(representatives)} node(s)")

        canonical, drop = self._propose_mapping(representatives, graph["relations"], det_map)
        llm_map = self._llm_alias_map(canonical, set(representatives))
        node_map = self._compose(nodes, det_map, llm_map, drop)
        cleaned = self._apply(graph, node_map)

        self._save(cleaned, output_path)
        logger.success(
            f"Cleaned proposal → {output_path} — "
            f"entities {len(graph['entities'])}→{len(cleaned['entities'])}, "
            f"relations {len(graph['relations'])}→{len(cleaned['relations'])}"
        )
        return cleaned

    # HELPERS -------------------------------------------------------------------------------------

    def _to_text(self, input_path: Path) -> str:
        suffix = input_path.suffix.lower()
        if suffix in (".md", ".txt"):
            return input_path.read_text(encoding="utf-8")
        if suffix in (".pdf", ".docx"):
            return self._docling.convert(str(input_path)).document.export_to_markdown()
        raise ValueError(f"Unsupported file extension: {suffix}")

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

    @staticmethod
    def _save(staging: dict, output_file_path: str) -> None:
        output_path = Path(output_file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(staging, f, ensure_ascii=False, indent=2)

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

    def _propose_mapping(self, nodes: list[str], relations: list[list], det_map: dict) -> tuple[dict, set]:
        prompt = clean_graph_nodes_prompt(self._nodes_block(nodes, relations, det_map))
        response = ollama.generate(model=config.KG_CLEANUP_LLM, think=False, prompt=prompt).response
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
    def _compose(nodes: list[str], det_map: dict, llm_map: dict, drop: set) -> dict:
        node_map = {}
        for n in nodes:
            rep = det_map.get(n, n)
            node_map[n] = None if rep in drop else llm_map.get(rep, rep)
        return node_map

    @staticmethod
    def _apply(graph: dict, node_map: dict) -> dict:
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