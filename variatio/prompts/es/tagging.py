"""The tagger's verification pass: which curriculum concepts an item makes a solver practise."""


def tag_concepts_prompt(
    statement: str,
    candidates: str,
    relations: str = "",
    context_block: str = "",
) -> str:
    """Ask which of the candidate concepts an item practises, and which one is its objective.

    The answer is `concepts` plus `primary_concept`, both drawn only from the candidate
    list, and `{"concepts": [], "primary_concept": null}` when none of them is what the item
    centrally practises. The two fields answer different questions: the primary is fixed
    first by the deciding test — could a student who has mastered everything except this
    concept still solve it? — and widening `concepts` afterwards may not change it. The
    candidates arrive with their descriptions and the relations among themselves, so the
    judgement is made on what a concept means here and not on its name.
    """
    context_section = f"\n# CONTEXTO DOCENTE\n{context_block}\n" if context_block.strip() else ""

    relations_block = ""
    if relations.strip():
        relations_block = (
            "\n# RELACIONES ENTRE LOS CANDIDATOS\n"
            "Relaciones del grafo del currículo entre los propios candidatos. Dicen cómo se ordenan estos conceptos en la secuencia de aprendizaje; úsalas para elegir el NIVEL DE ESPECIFICIDAD correcto:\n"
            f"{relations}\n"
        )

    return f"""\
Estás catalogando el banco de ejercicios de una asignatura. Para el ejercicio de abajo, decide QUÉ CONCEPTOS DEL CURRÍCULO hace practicar a quien lo resuelve.
{context_section}
# CONCEPTOS CANDIDATOS
Ordenados de mayor a menor relevancia semántica respecto al enunciado. Bajo cada nombre está la descripción del concepto: describe la tarea que se le plantea al alumno cuando lo practica. Juzga por la descripción, no por el nombre.
{candidates}
{relations_block}
# DISTINCIÓN CENTRAL: PRACTICAR NO ES USAR
Todo ejercicio USA muchos conceptos y PRACTICA unos pocos. Aquí se etiqueta lo que PRACTICA.
- Un concepto se PRACTICA si el ejercicio pone a prueba lo que el alumno sabe hacer con él.
- Un concepto se USA cuando aparece como vehículo, soporte o notación de la tarea, pero se da por dominado y el ejercicio no lo ejercita en absoluto.
- PRUEBA DECISIVA, Y ES LA DEL PRIMARIO: imagina un alumno que domina todo lo demás salvo ese concepto. ¿Resolvería el ejercicio igualmente? Si la respuesta es sí, ese concepto no es el OBJETIVO del ejercicio.
- Los dos campos de salida se deciden con preguntas DISTINTAS: la de arriba fija `primary_concept`; `concepts` responde a otra más amplia, descrita en las reglas.

# ESQUEMA DE SALIDA
{{
  "concepts": ["Concepto A", "Concepto B"],
  "primary_concept": "Concepto A"
}}

# REGLAS
- Usa ÚNICAMENTE conceptos de la lista de candidatos. No inventes ni parafrasees nombres.
- ORDEN DE DECISIÓN: fija PRIMERO el primario, aplicando solo la prueba decisiva y sin pensar todavía en la lista. Solo después amplía a `concepts`. Ampliar la lista no puede cambiar el primario que ya fijaste.
- `primary_concept`: UNO SOLO, el OBJETIVO DE APRENDIZAJE del ejercicio — aquello que el ejercicio existe para poner a prueba, lo que se evaluaría con él. Aquí aplica la prueba decisiva sin concesiones. Debe aparecer también en `concepts`.
- `concepts`: el primario MÁS todo concepto que este ejercicio sirva para practicar, aunque no sea su objetivo central. La pregunta aquí es más amplia y es ésta: un docente que buscase ejercicios para trabajar ese concepto, ¿se alegraría de encontrar éste? Si la respuesta es sí, va en la lista.
- Lo que sigue quedando FUERA de `concepts`: lo que el enunciado solo menciona, lo que usa como pura notación y lo que da por sabido sin ejercitarlo en absoluto. Amplio no es indiscriminado.
- CUÁNTOS: dos o tres es lo normal, cuatro el máximo. Si pasas de cuatro has colado herramientas.
- ESPECIFICIDAD: entre dos candidatos donde uno es un tipo de otro, o parte de otro, el primario es el MÁS ESPECÍFICO que el ejercicio practique de verdad. El general puede acompañarlo en `concepts`.
- SECUENCIA DE APRENDIZAJE: si un candidato es prerrequisito de otro y ambos aparecen, el PRIMARIO es normalmente el posterior. El prerrequisito va en `concepts` si el ejercicio lo ejercita, no si solo se apoya en él.
- El orden de los candidatos es una pista, no una respuesta: el primero no tiene por qué ser el primario.
- Un solo elemento en `concepts` solo si el ejercicio de verdad no practica nada más.
- Si NINGÚN candidato es aquello que el ejercicio practica de forma central, devuelve {{"concepts": [], "primary_concept": null}}. Usa esta opción con criterio: solo cuando ningún candidato describa el objetivo real del ejercicio, no ante mera incertidumbre.
- Responde SOLO con el JSON. Sin texto antes ni después, sin backticks, sin comentarios.

# EJERCICIO A ETIQUETAR
{statement}

JSON:"""
