from ggleg.concept_tagger import ConceptTagger
from ggleg.embedder import Embedder
from ggleg.exercise_formatter import ExerciseFormatter
from ggleg.knowledge_graph import KnowledgeGraph
from ggleg.utils import load_exercises_dataset

RAW_BANK_PATH = "data/formatted_exercises_es_local.json"
ANNOTATED_BANK_PATH = "data/formatted_exercises_es_annotated.json"
KG_PATH = "data/knowledge_graph_raw.json"

if __name__ == "__main__":
    # Paso 1 — formatear workbooks → banco raw con statement/solution/notebook
    formatter = ExerciseFormatter()
    formatter.format_dir("./workbooks", RAW_BANK_PATH)

    # Paso 2 — anotar conceptos y calcular dificultad desde KG
    kg = KnowledgeGraph(KG_PATH)
    raw_bank = load_exercises_dataset(f"../{RAW_BANK_PATH}")

    embedder = Embedder(kg.all_concepts, raw_bank)
    tagger = ConceptTagger(kg, embedder)
    tagger.tag_all(raw_bank, output_path=ANNOTATED_BANK_PATH)

    # Paso 3 — reconstruir Embedder con banco anotado (centroids enriquecidos + exercise index)
    annotated_bank = load_exercises_dataset(f"../{ANNOTATED_BANK_PATH}")
    Embedder(kg.all_concepts, annotated_bank)
