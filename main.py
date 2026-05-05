from loguru import logger

from system import config
from system.concept_tagger import ConceptTagger
from system.content_bank import ContentBank
from system.embedder import Embedder
from system.knowledge_graph import KnowledgeGraph
from system.utils import load_manifest

# Paths
KG_PATH = "essential_data/knowledge_graph_raw.json"
CONTENT_BANK_PATH = "essential_data/content_bank/formatted_content_bank.json"
RAW_BANK_DIR = "essential_data/content_bank/raw_content_bank"
MANIFEST_PATH = "essential_data/manifest_student.py"


def initialize_essentials():
    manifest = load_manifest(MANIFEST_PATH)

    graph = KnowledgeGraph(KG_PATH)
    embedder = Embedder(graph, config.EMBEDDING_LLM)
    tagger = ConceptTagger(graph, embedder, config.CONCEPT_TAGGER_LLM)

    content_bank = ContentBank(manifest.item_model, manifest.context)
    
    content_bank.format_file("./essential_data/raw_content_bank/WB1.docx", "o.json")

    return manifest, graph, embedder, tagger, content_bank


def processing_pipeline(query: str, graph, embedder):
    logger.info(f'Query: "{query}"')
    top_concepts = embedder.top_k_concepts(query, k=5)
    for rank, (concept, score) in enumerate(top_concepts, 1):
        domain = graph.concept_domain[concept]
        logger.info(f"{rank}. {concept} (score: {score:.3f}) — {domain}")


if __name__ == "__main__":
    manifest, graph, embedder, tagger, generator, content_bank = initialize_essentials()
