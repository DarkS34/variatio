from pathlib import Path

from loguru import logger

from .. import config, inference


def _upstream():
    try:
        import kg_builder
    except ImportError as e:
        raise ImportError(
            "Building the knowledge graph needs kg-builder, which is an optional extra. "
            "Install it with: uv sync --extra builders"
        ) from e
    return kg_builder


class KnowledgeGraphBuilder:
    def __init__(self, verbose: bool = True):
        logger.enable(__name__) if verbose else logger.disable(__name__)

        upstream = _upstream()
        self._builder = upstream.KnowledgeGraphBuilder(
            config=upstream.BuilderConfig(
                extraction_model=config.KG_BUILDER_EXTRACTION_MODEL,
                curation_model=config.KG_BUILDER_CURATION_MODEL,
                repair_model=config.REPAIR_LLM,
                ollama_host=config.OLLAMA_HOST,
                chunk_size=config.KG_BUILDER_CHUNK_SIZE,
                max_repair_attempts=config.MAX_JSON_REPAIR_TRIES,
                merge_qualifier_pattern=config.KG_BUILDER_MERGE_QUALIFIER_PATTERN,
                unclassified_domain=config.KG_BUILDER_UNCLASSIFIED_DOMAIN,
                output_dir=config.INSTANCE_DIR,
            ),
            relations=upstream.BUILTIN_SCHEMAS[config.KG_RELATION_SCHEMA],
            engine=inference,
            verbose=verbose,
        )

    def build(self, input_dir: str | Path) -> dict:
        self._builder.bootstrap()

        staging = self._builder.build(input_dir)
        if not staging:
            raise RuntimeError(f"No knowledge graph could be extracted from: {input_dir}")

        self._builder.clean()
        return self._builder.curate()
