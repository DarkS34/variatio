from loguru import logger

from essential_data.manifest_student import CONTEXT, GENERATION_RULES, ContentItem
from system import config
from system.concept_tagger import ConceptTagger
from system.content_bank import ContentBank
from system.content_generator import ContentGenerator
from system.embedder import Embedder
from system.knowledge_graph import KnowledgeGraph

if __name__ == "__main__":
    graph = KnowledgeGraph(config.KG_PATH)
    content_bank = ContentBank(ContentItem, CONTEXT)

    embedder = Embedder(
        graph,
        config.EMBEDDING_LLM,
        primary_field=ContentItem.PRIMARY_FIELD,
        context=CONTEXT,
    )
    tagger = ConceptTagger(
        embedder, config.CONCEPT_TAGGER_LLM, primary_field=ContentItem.PRIMARY_FIELD
    )

    if not content_bank.bank:
        content_bank.format_dir(config.RAW_CONTENT_BANK_DIR, config.CONTENT_BANK_PATH)

    # annotated_bank = tagger.tag_all(content_bank.bank, config.CONTENT_BANK_PATH)
    # embedder.enrich_index_with_content(annotated_bank)

    generator = ContentGenerator(
        knowledge_graph=graph,
        content_bank=content_bank.bank,
        embedder=embedder,
        item_model=ContentItem,
        context=CONTEXT,
        generation_rules=GENERATION_RULES,
        generator_model=config.CONTENT_GENERATION_LLM,
    )

    results = generator.generate(concepts=["Bucle", "Lista"], difficulty=2, n=2)
    for i, r in enumerate(results, 1):
        logger.info(f"\n--- Generated item {i} ---")
        if r.thinking:
            logger.info(f"THINKING:\n{r.thinking}")
        logger.info(f"ITEM:\n{r.item.model_dump_json(indent=2)}")
