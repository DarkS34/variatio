from ggleg.exercise_formatter import ExerciseFormatter

student = {
    "mastered": [
        "Variable",
        "Expresión",
        "Entrada / Salida",
        "Sentencia condicional",
    ]
}


if __name__ == "__main__":
    formatter = ExerciseFormatter()
    formatter.format_dir("./workbooks", "formatted_exercises_es.json")