from didactic_system.data.student_profiles import STUDENTS
from didactic_system.didactic_agent import DidacticAgent

if __name__ == "__main__":
    stundent_1 = STUDENTS[0]
    agent = DidacticAgent(stundent_1, gen_LLM="gemma4:e4b-it-q4_K_M")
    validated_input = agent.free_interaction()
    relevant_concepts = agent.embedder.label_concepts_with_scores(validated_input)
    print(relevant_concepts)