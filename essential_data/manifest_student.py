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
        description=(
            "Enunciado del ejercicio en español, redactado en prosa breve y autocontenida. "
            "Debe indicar con claridad qué tiene que hacer el programa y, cuando aplique, qué datos recibe y qué se muestra por pantalla. "
            "No incluyas pistas de implementación ni la solución."
        ),
    )
    difficulty: Literal[1, 2, 3, 4] = Field(
        description=(
            "Nivel de dificultad del ejercicio. "
            "1 (Fácil): 1-2 conceptos del grafo; sin control de flujo ni colecciones; una sola expresión o condición. "
            "2 (Medio): 3-5 conceptos; varias expresiones o un condicional; mínima modularidad. "
            "3 (Difícil): 5-8 conceptos; usa bucles o colecciones; exige planificar el algoritmo y admite múltiples rutas. "
            "4 (Avanzado): 8+ conceptos; recursividad, algoritmos clásicos o varias colecciones combinadas; alta carga cognitiva."
        )
    )
    solution: str | None = Field(
        default=None,
        description=(
            "Solución del ejercicio como código Python ejecutable que resuelve lo pedido en el enunciado. "
            "Si el documento original incluye la solución, cópiala literalmente sin reformatear ni optimizar; si no existe, deja el campo en null. "
            "Texto plano, sin fences de Markdown."
        ),
    )


GENERATION_RULES = [
    "El enunciado debe tener libertad creativa y ser original; no copies los ejemplos.",
    "La solución solo puede usar conceptos ya vistos por el alumno — evita construcciones más elegantes pero desconocidas.",
    "Solo built-ins de Python: nada de librerías externas.",
    "Evita enunciados puramente matemáticos sin contexto narrativo.",
]