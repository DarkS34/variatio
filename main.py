from didactic_system.didactic_agent import DidacticAgent

student1 = {
    "student_id": "S001",
    "mastered": [
        "Variable",
        "Expresión",
        "Entrada / Salida",
        "Sentencia condicional",
    ],
}
student2 = (
    {
        "student_id": "S002",
        "mastered": [
            "Variable",
            "Expresión",
            "Entrada / Salida",
            "Sentencia condicional",
            "Bucle for",
            "Bucle while",
            "Función",
            "Lista",
            "Diccionario",
        ],
    },
)
student3 = {
    "student_id": "S003",
    "mastered": [
        "Variable",
        "Expresión",
        "Entrada / Salida",
        "Sentencia condicional",
        "Bucle for",
        "Bucle while",
        "Función",
        "Recursividad",
        "Lista",
        "Diccionario",
        "Cadena",
        "Tupla",
    ],
}


if __name__ == "__main__":
    agent = DidacticAgent(student1, )
    agent.format_excercises("./Cuaderno de trabajo 1.docx", "o.md")
    # validated_input = agent.interaction()
    # relevant_concepts = agent.embedder.label_concepts_with_scores(validated_input)
    # print(relevant_concepts)
