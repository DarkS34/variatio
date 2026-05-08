from essential_data.manifest_student import CONTEXT, ContentItem
from system import config
from system.concept_tagger import ConceptTagger
from system.content_bank import ContentBank
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

    annotated_bank = tagger.tag_all(content_bank.bank, config.CONTENT_BANK_PATH)
    embedder.enrich_index_with_content(annotated_bank)