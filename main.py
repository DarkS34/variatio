from ggleg.concept_tagger import ConceptTagger
from ggleg.embedder import Embedder
from ggleg.knowledge_graph import KnowledgeGraph
from ggleg.utils import ModelRegistry, load_exercises_dataset


KG_PATH = "data/knowledge_graph_raw.json"
RAW_BANK_PATH = "data/formatted_exercises_test.json"
ANNOTATED_BANK_PATH = "data/formatted_exercises-concept_tagged.json"



if __name__ == "__main__":
    models = ModelRegistry()

    KG = KnowledgeGraph(KG_PATH)

    # Fase 1: Embedder con nombre-embeddings de concepto (cacheados)
    embedder = Embedder(KG.all_concepts, embedding_model=models.embedding("embed"))

    # ConceptTagger consume el Embedder ya construido — usa su top_k_concepts
    tagger = ConceptTagger(KG, embedder=embedder, llm=models.llm("tag_concepts"))

    raw_bank = load_exercises_dataset(RAW_BANK_PATH)
    annotated_bank = tagger.tag_all(raw_bank, output_path=ANNOTATED_BANK_PATH)

    # Fase 2: enriquece centroides con ejercicios anotados (sin re-embedrar conceptos)
    embedder.enrich_with_exercises(annotated_bank)
