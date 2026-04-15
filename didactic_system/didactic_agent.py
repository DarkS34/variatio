import ollama
import json
from loguru import logger
from didactic_system.utils import ExerciseFormatter
from didactic_system.embedder import Embedder
from didactic_system.knowledge_graph import KnowledgeGraph
from didactic_system.utils import load_exercises_dataset
from didactic_system.workflow_prompts import get_input_validation_prompt


class DidacticAgent:
    def __init__(self, 
                 student_info: dict, 
                 raw_kg_path: str = "data/concepts_relations_es.json", 
                 formatted_exercises_path: str = "data/formatted_exercises_es.json"):
        
        self.gen_LLM = "gemma4:e4b-it-q4_K_M"
        self.exercises_dataset = load_exercises_dataset(formatted_exercises_path)
        self.knowledge_graph = KnowledgeGraph(raw_kg_path)
        self.embedder = Embedder(self.knowledge_graph.all_concepts, self.exercises_dataset)
        
        self.student_mastered = set(student_info["mastered"])
        self.student_history = []

    def format_excercises(self, input_path: str, output_path:str):
        self.ef = ExerciseFormatter()
        self.ef.convert_file(input_path, output_path)


    def free_interaction(self, max_retries:int = 5):
        
        def _validate_user_input(user_input: str):
            try:
                response = ollama.generate(model=self.gen_LLM,
                                           prompt=get_input_validation_prompt(user_input),
                                           format="json",
                                           options={
                                               "num_predict": 100,"temperature": 0.1,
                                               "top_p": 0.5,
                                               "repeat_penalty": 1.1,
                                               }
                                           )

                response_text = response.get("response", "").strip()
                logger.debug(f"Validación LLM response: {response_text}")

                parsed = json.loads(response_text)

                if parsed["valid"]:
                    return {
                        "valid": True,
                        "message": "Input válido",
                        "cleaned_input": parsed.get("cleaned_input", user_input),
                    }
                else:
                    return {
                        "valid": False,
                        "message": f"Input no válido: {parsed.get('reason', 'Razón desconocida')}",
                        "cleaned_input": None,
                    }

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error al parsear respuesta del LLM: {e}")
                # Fallback: validación basada en reglas simples
                if not user_input or len(user_input.strip()) == 0:
                    return {
                        "valid": False,
                        "message": "Error: La entrada no puede estar vacía. Por favor intenta de nuevo.",
                        "cleaned_input": None,
                    }
                return {
                    "valid": True,
                    "message": "Input válido",
                    "cleaned_input": user_input.strip(),
                }
        
        
        validated_input = None

        for attempt in range(max_retries):
            user_input = input(">> ")
            validation_result = _validate_user_input(user_input)

            if validation_result["valid"]:
                validated_input = validation_result["cleaned_input"]
                break
            else:
                if attempt < max_retries - 1:
                    logger.info(f"Por favor intenta de nuevo ({max_retries - attempt - 1} intentos restantes):")
                else:
                    logger.error("Se alcanzó el límite de intentos. Sesión finalizada.")
                    exit()

        # self.student_history.append({"input": validated_input, "timestamp": None})

        return validated_input
