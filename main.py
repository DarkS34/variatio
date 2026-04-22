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
    formatter.format_file("./workbooks/Cuaderno de trabajo 1.docx", "o.json")
    