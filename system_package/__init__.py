from system_package.knowledge_graph import CurriculumGraph

from .utils import is_ollama_connected

if not is_ollama_connected():
    raise ConnectionError("Cannot connect to Ollama. Make sure Ollama is running before initializing the agent.")

kg = CurriculumGraph()
kg.visualize()