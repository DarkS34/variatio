from system import config
from loguru import logger
from system.adaptative_content_generator import AdaptativeContentGenerator
from system.concept_tagger import ConceptTagger
from system.content_bank import ContentBank
from system.embedder import Embedder
from system.knowledge_graph import KnowledgeGraph
from system.utils import load_context


# Paths
KG_PATH = "essential_data/knowledge_graph_raw.json"
CONTENT_BANK_PATH = "essential_data/content_bank/formatted_content_bank.json"
RAW_BANK_DIR = "essential_data/content_bank/raw_content_bank"
CONTEXT_PATH = "essential_data/context.json"


def initialize_essentials():
    context = load_context(CONTEXT_PATH)

    content_bank = ContentBank(
        item_model=context["item_model"],
        context_name=context["context"],
    )

    graph = KnowledgeGraph(KG_PATH)
    embedder = Embedder(graph, config.EMBEDDING_LLM)
    tagger = ConceptTagger(graph, embedder, config.CONCEPT_TAGGER_LLM)



    content_bank = ContentBank.load_content_bank(CONTENT_BANK_PATH)
    embedder.enrich_index_with_content(content_bank)

    generator = AdaptativeContentGenerator(
        model=config.CONTENT_FORMATTING_LLM,
        embedder=embedder,
        bank=content_bank,
        knowledge_graph=graph,
        allowed_domains=context["allowed_domains"],
        generation_context=context["generation_context"],
    )

    return context, graph, embedder, tagger, handler, generator, content_bank


def processing_pipeline(query: str, graph, embedder):
    logger.info(f"Query: \"{query}\"")
    top_concepts = embedder.top_k_concepts(query, k=5)
    for rank, (concept, score) in enumerate(top_concepts, 1):
        domain = graph.concept_domain[concept]
        logger.info(f"{rank}. {concept} (score: {score:.3f}) — {domain}")


if __name__ == "__main__":
    context, graph, embedder, tagger, handler, generator, content_bank = initialize_essentials()

    