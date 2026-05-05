from typing import Literal

from pydantic import BaseModel, Field

CONTEXT = {
    "subject": "Programación 1",
    "level": "Primer curso universitario, sin experiencia previa en programación",
    "language": "Python",
    "constraints": "Los ejercicios deben ser directos y autónomos, sin depender de código externo",
}


class ContentItem(BaseModel):
    statement: str = Field(
        min_length=20,
        description="Enunciado completo del ejercicio, autocontenido y en prosa",
    )
    solution: str | None = Field(
        default=None,
        description="Solución en Python, si aparece en el documento. Mantén el código tal cual aparece en la fuente.",
    )
    difficulty: Literal[1, 2, 3, 4] = Field(
        description=(
            "Nivel de dificultad del ejercicio. "
            "1 (Fácil): 1-2 conceptos del grafo; sin control de flujo ni colecciones; una sola expresión o condición. "
            "2 (Medio): 3-5 conceptos; varias expresiones o un condicional; mínima modularidad. "
            "3 (Difícil): 5-8 conceptos; usa bucles o colecciones; exige planificar el algoritmo y admite múltiples rutas. "
            "4 (Avanzado): 8+ conceptos; recursividad, algoritmos clásicos o varias colecciones combinadas; alta carga cognitiva."
        ),
    )


GENERATION_RULES = [
    "El enunciado debe tener libertad creativa y ser original; no copies los ejemplos.",
    "La solución solo puede usar conceptos ya vistos por el alumno — evita construcciones más elegantes pero desconocidas.",
    "Solo built-ins de Python: nada de librerías externas.",
    "Evita enunciados puramente matemáticos sin contexto narrativo.",
]
