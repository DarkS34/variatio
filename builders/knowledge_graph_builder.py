import json
from pathlib import Path

from docling.document_converter import DocumentConverter, InputFormat
from kg_gen import KGGen
from loguru import logger

from system import config


class KnowledgeGraphBuilder:
    SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")

    def __init__(self, model: str = config.KG_BUILDER_LLM, verbose: bool = True):
        logger.enable(__name__) if verbose else logger.disable(__name__)

        self._docling = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX])

        # kg-gen habla con Ollama vía litellm: hace falta el prefijo de proveedor y el api_base
        # explícito. Ollama ignora api_key, pero litellm exige un valor no vacío.
        self._kg = KGGen(
            model=f"ollama_chat/{model}",
            api_base=config.OLLAMA_HOST,
            api_key="ollama",
            temperature=0.0,
        )
        self.chunk_size = config.KG_BUILDER_CHUNK_SIZE

    # build() vuelca el grafo NATIVO de kg-gen a un artefacto de staging; el moldeado al esquema
    # curado de knowledge_graph.json (dominios, relaciones tipadas, no-etiquetables) es manual.
    def build(
        self,
        input_dir: str,
        output_file_path: str,
        context: str = "",
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

        graphs = []
        for idx, file_path in enumerate(files, 1):
            tag = f"[{idx}/{len(files)} {file_path.name}]"
            try:
                text = self._to_text(file_path)
                logger.info(f"{tag} text ready ({len(text):,} chars) - extracting")
                graph = self._kg.generate(
                    input_data=text,
                    context=context,
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


if __name__ == "__main__":
    KnowledgeGraphBuilder().build(config.RAW_KNOWLEDGE_GRAPH_DIR, config.KG_STAGING_PATH)
