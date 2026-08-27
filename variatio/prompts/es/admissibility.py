def classify_instructions_prompt(
    instructions: str,
    catalog,
    owners,
    targets: list[str],
    context_block: str = "",
) -> str:
    context_section = ""
    if context_block.strip():
        context_section = f"\n# CONTEXTO DOCENTE\n{context_block}\n"

    slots = "\n".join(f"- {s.key}: {s.label}. Por ejemplo, «{s.example}»" for s in catalog)

    owner_lines = []
    for owner in owners:
        terms = ", ".join(f"«{t}»" for t in owner.terms)
        owner_lines.append(f"- {owner.key} ({owner.label}) decide: {terms}")
    owners_block = "\n".join(owner_lines)

    targets_block = ", ".join(f"«{t}»" for t in targets) or "(ninguno)"

    # The owners are derived per instance, so an example about a control that may not
    # exist teaches the model to attribute the request to the nearest owner it can see.
    # Measured: with no `field:` owner, «que sea muy difícil» came back as an invasion of
    # `concepts` («Complejidad asintótica») and «que el nivel de dificultad sea básico» as
    # one of `item_type` («escritura_codigo»), both nonsense.
    if any(owner.key.startswith("field:") for owner in owners):
        difficulty_rule = (
            "- «que sea muy difícil» fija la exigencia, y arriba hay un control que la "
            "decide: invade ese control."
        )
    else:
        difficulty_rule = (
            "- «que sea muy difícil» fija la exigencia, y arriba NO hay ningún control que "
            "la decida: no invade nada. No se la atribuyas al dueño que más se le parezca."
        )

    return f"""\
Clasificas la petición que ha escrito quien encarga un ejercicio. No escribes el ejercicio ni opinas sobre él: solo dices, para cada cosa que pide, si es de las que puede pedir aquí o si es de las que ya ha decidido en otro sitio.
{context_section}
# LO QUE SÍ SE PIDE AQUÍ
Cuatro huecos. Una petición que encaje en uno de ellos es admisible:
{slots}

# LO QUE YA ESTÁ DECIDIDO EN OTRO SITIO
Cada línea es un control del formulario y lo que ese control decide. Una petición que invada uno de ellos NO es admisible, y hay que decir cuál invade y con qué término exacto de la lista:
{owners_block}

# LOS CONCEPTOS OBJETIVO DE ESTE ENCARGO
{targets_block}
Pedir algo sobre ellos NO es invadir nada: son el tema del ejercicio. Solo es invasión pedir que se practique un concepto que NO está en esta línea.

# LA PRUEBA
Un ejercicio USA muchos conceptos y PRACTICA uno o dos. La pregunta, para cada petición, es cuál de las dos cosas pide.
- «que vaya de una lista de la compra» USA la palabra lista como escenario de la vida real: es el hueco `ambito`, no el concepto «Lista».
- «que vaya de una biblioteca que presta libros» es un edificio con libros: es `ambito`.
- «con un ejemplo de entrada y salida» pide que el enunciado enseñe un caso resuelto: es el hueco `elementos`, aunque el nombre de un concepto aparezca dentro de la frase.
- «que practique también recursividad» pide PRACTICAR un concepto: invade `concepts`.
{difficulty_rule}
- «hazlo en inglés» cambia el idioma, que lo fija la asignatura: invade `context`.
Que una palabra del texto coincida con el nombre de un concepto NO es una invasión: solo lo es pedir que ese concepto se PRACTIQUE.
Un dueño solo se puede invadir si está en la lista de arriba. Si lo que se pide no encaja en ningún hueco y ningún dueño listado lo decide, deja `slot` y `owner` a `null`: no es asunto de esta pantalla ni de ninguna otra.
Ante la duda entre un hueco y un dueño, gana el hueco: rechazar una petición legítima cuesta más que dejar pasar una dudosa.

# LA PETICIÓN A CLASIFICAR
«{instructions.strip()}»

# LA SALIDA
Un objeto JSON con la clave `requests`: una entrada por cada cosa distinta que se pide en el texto. Un texto que pide dos cosas da dos entradas.
Cada entrada lleva:
- `text`: el trozo del texto original al que se refiere, copiado tal cual.
- `slot`: la clave del hueco si es admisible; `null` si no.
- `owner`: la clave del dueño invadido si no lo es; `null` si lo es.
- `term`: el término EXACTO de la lista de ese dueño, copiado carácter por carácter; `null` si `slot` no es `null`.
Nunca rellenes `slot` y `owner` a la vez. Nunca inventes un término que no esté en la lista del dueño.
Nada antes ni después del objeto. Sin ```json, sin comentarios."""
