# from loguru import logger

from system import config
from system.concept_tagger import ConceptTagger
from system.content_bank import ContentBank
from system.content_generator import ContentGenerator
from system.embedder import Embedder
from system.knowledge_graph import KnowledgeGraph
from system.manifest import Manifest

if __name__ == "__main__":
    manifest = Manifest(config.MANIFEST_PATH)
    graph = KnowledgeGraph(config.KG_PATH)
    content_bank = ContentBank(manifest)

    embedder = Embedder(
        graph,
        config.EMBEDDING_LLM,
        primary_field=manifest.primary_field,
        context=manifest.content_context,
    )
    tagger = ConceptTagger(
        embedder, config.CONCEPT_TAGGER_LLM, primary_field=manifest.primary_field
    )

    if not content_bank.bank:
        content_bank.format_dir(config.RAW_CONTENT_BANK_DIR, config.CONTENT_BANK_PATH)

    # annotated_bank = tagger.tag_all(content_bank.bank, config.CONTENT_BANK_PATH)
    # embedder.enrich_index_with_content(annotated_bank)

    generator = ContentGenerator(
        knowledge_graph=graph,
        content_bank=content_bank.bank,
        embedder=embedder,
        manifest=manifest,
        generator_model=config.CONTENT_GENERATION_LLM,
    )

    results = generator.generate(concepts=["Bucle", "Lista"], difficulty=4)

    # TODO validator

    # for i, r in enumerate(results, 1):
    #     logger.info(f"\n--- Generated item {i} ---")
    #     if r.thinking:
    #         logger.info(f"THINKING:\n{r.thinking}")
    #     logger.info(f"ITEM:\n{r.item.model_dump_json(indent=2)}")
