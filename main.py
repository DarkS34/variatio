from ggleg.concept_tagger import ConceptTagger
from ggleg.embedder import Embedder
from ggleg.exercise_formatter import ExerciseFormatter
from ggleg.knowledge_graph import KnowledgeGraph
from ggleg.utils import ModelRegistry, load_exercises_dataset

KG_PATH = "data/knowledge_graph_raw.json"
RAW_BANK_PATH = "data/formatted_exercises_test.json"
ANNOTATED_BANK_PATH = "data/formatted_exercises-concept_tagged.json"


if __name__ == "__main__":
    # Phase 0: Initialize esentials
    models = ModelRegistry()
    knowledge_graph = KnowledgeGraph(KG_PATH)
    embedder = Embedder(knowledge_graph.all_concepts, embedding_model=models.embedding("embed"))
    tagger = ConceptTagger(knowledge_graph, embedder=embedder, llm=models.llm("tag_concepts"))

    # Phase 0.1: Format exercises or import existing formatted exercises
    ExerciseFormatter(llm=models.llm("format_exercises")).format_dir(input_dir="./workbooks", output_file_path=RAW_BANK_PATH)
    raw_bank = load_exercises_dataset(RAW_BANK_PATH)

    # Phase 0.2: Tag all existing exercises
    annotated_bank = tagger.tag_all(raw_bank, output_path=ANNOTATED_BANK_PATH)

    # Phase 0.3: Enrich embeddings with tagged exercises
    embedder.enrich_with_exercises(annotated_bank)
    
    # TODO Phase 1: Take user query
