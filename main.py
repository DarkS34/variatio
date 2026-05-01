from system.concept_tagger import ConceptTagger
from system.embedder import Embedder
from system.content_bank_handler import ContentBankHandler
from system.knowledge_graph import KnowledgeGraph
from system.utils import load_models

KG_PATH = "data/knowledge_graph_raw.json"
RAW_BANK_PATH = "data/formatted_exercises.json"
ANNOTATED_BANK_PATH = "data/formatted_exercises-concept_tagged.json"


if __name__ == "__main__":
    # Load model into memory
    models = load_models()
    
    # Phase 0: Initialize esentials
    knowledge_graph = KnowledgeGraph(KG_PATH)
    # content_bank_handler = ContentBankHandler(llm=models.get("format_exercises"))
    print(knowledge_graph.neighbors("Variable", "tiene como prerrequisito"))
    
    
    # embedder = Embedder(knowledge_graph, embedding_model=models.get("embedding"))
    # tagger = ConceptTagger(knowledge_graph=knowledge_graph, embedder=embedder, llm=models.get_generative_LLM("tag_concepts"))

    # # Phase 0.1: Format exercises or import existing formatted exercises
    # raw_bank = content_bank_handler.format_dir(input_dir="./workbooks", output_file_path=RAW_BANK_PATH)

    # # Phase 0.2: Tag all existing exercises
    # annotated_bank = tagger.tag_all(raw_bank, output_path=ANNOTATED_BANK_PATH)

    # # Phase 0.3: Enrich embeddings with tagged exercises
    # embedder.enrich_with_exercises(annotated_bank)