from loguru import logger
from ggleg.embedder import Embedder
from ggleg.knowledge_graph import KnowledgeGraph
from ggleg.utils import load_exercises_dataset


class DidacticAgent:
    def __init__(self, student_info: dict, raw_kg_path: str = "data/knowledge_graph_raw.json", formatted_exercises_path: str = "data/formatted_exercises_es.json"):
        self.gen_LLM = "gemma4:e4b-it-q4_K_M"
        self.exercises_dataset = load_exercises_dataset(formatted_exercises_path)
        self.knowledge_graph = KnowledgeGraph(raw_kg_path)
        self.embedder = Embedder(self.knowledge_graph.all_concepts, self.exercises_dataset)
        
        self.student_mastered = set(student_info["mastered"])
        self.student_history = []
