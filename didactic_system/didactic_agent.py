from didactic_system.didactic_embedder import DidacticEmbedder
from didactic_system.knowledge_graph import KnowledgeGraph
from didactic_system.utils import load_exercises_dataset

MODELS = {}

class DidacticAgent:
    def __init__(self, gen_LLM:str, mode: str = "student"):
        self.gen_LLM = gen_LLM
        self.exercises_dataset = load_exercises_dataset()
        self.knowledge_graph = KnowledgeGraph()
        self.didactic_embedder = DidacticEmbedder(self.knowledge_graph.all_concepts, )