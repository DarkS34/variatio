from ggleg.concept_tagger import ConceptTagger
from ggleg.embedder import Embedder
from ggleg.exercise_formatter import ExerciseFormatter
from ggleg.knowledge_graph import KnowledgeGraph
from ggleg.utils import ModelRegistry


KG_PATH = "config/data/knowledge_graph_raw.json"

RAW_BANK_PATH = "data/formatted_exercises.json"
ANNOTATED_BANK_PATH = "data/formatted_exercises_annotated.json"



if __name__ == "__main__":
    models = ModelRegistry()

    KG = KnowledgeGraph(KG_PATH)

    # raw_bank = ExerciseFormatter(llm=models.llm("0_format_exercises")).format_dir("./workbooks", RAW_BANK_PATH)

    tagger = ConceptTagger(KG, llm=models.llm("1_tag_concepts"), embedding_model=models.embedding("2_embed"))
    
    # annotated_bank = tagger.tag_all(raw_bank, output_path=ANNOTATED_BANK_PATH)

    # embedder = Embedder(KG.all_concepts,annotated_bank,embedding_model=models.embedding("2_embed"))
