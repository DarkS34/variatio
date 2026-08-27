def describe_domain_concepts_prompt(
    domain: str,
    concepts_block: str,
    passages_block: str,
    context_block: str,
    domains_block: str = "",
    existing_block: str = "",
) -> str:
    existing_section = (
        "\n# DESCRIPCIONES YA ESCRITAS DE ESTE MISMO BLOQUE (NO las reescribas)\n"
        "Estos conceptos ya tienen descripción y no te toca tocarlos. Están aquí porque compiten contra las tuyas: "
        "ninguna de las que escribas puede solaparse con éstas. No copies su estructura ni su voz.\n"
        f"{existing_block}\n"
        if existing_block.strip()
        else ""
    )
    context_section = f"\n# CONTEXTO DOCENTE\n{context_block}\n" if context_block.strip() else ""
    domains_section = (
        f"\n# EL TEMARIO ENTERO (contexto: los otros bloques existen y tienen sus propios conceptos)\n{domains_block}\n"
        if domains_block.strip()
        else ""
    )
    passages_section = (
        "\n# MATERIAL DE TEORÍA (LITERAL) Y QUÉ CONCEPTOS SALIÓ DE CADA FRAGMENTO\n"
        "Cada fragmento se muestra UNA vez, con la lista de los conceptos de este bloque que se extrajeron de él.\n"
        "- Es la única prueba de qué significan estos conceptos EN ESTA ASIGNATURA: toma de aquí el vocabulario, la notación y el nivel.\n"
        "- Un fragmento que produjo VARIOS conceptos trata de uno de ellos y menciona los demás de pasada. Ésa es justo la trampa: no describas a todos con el asunto del fragmento. Pregúntate, para cada uno, qué hace ÉL aquí que no hagan los otros.\n"
        "- Un concepto sin fragmento se describe por su nombre, sus relaciones y el temario.\n\n"
        f"{passages_block}\n"
        if passages_block.strip()
        else ""
    )
    return f"""\
Estás escribiendo, DE UNA VEZ, las descripciones de un grupo de conceptos del bloque temático «{domain}».
{context_section}{domains_section}{passages_section}{existing_section}
# PARA QUÉ SIRVEN ESTAS DESCRIPCIONES
Cada descripción es la superficie con la que se decidirá, para cada ejercicio del material docente, QUÉ CONCEPTO DEL CURRÍCULO PRACTICA ese ejercicio. Se compara semánticamente contra el enunciado de los ejercicios, así que cada una debe LEER COMO el enunciado de un ejercicio de ese concepto, o como su primera frase — no como la definición de manual del concepto.

Describe LA TAREA que se practica: lo observable que hay que hacer, no la teoría que hay detrás.

# POR QUÉ SE ESCRIBEN TODAS JUNTAS (LO MÁS IMPORTANTE)
Estas descripciones van a COMPETIR entre sí: se comparan todas contra el mismo ejercicio y solo una debe encajar. Escribirlas a la vez existe para que puedas separarlas, y ésa es tu tarea principal.

- Ninguna descripción puede describir igual de bien a otro concepto de esta misma lista. Si dos tuyas encajarían con el mismo ejercicio, están mal las dos.
- PROHIBIDO redactar dos descripciones con la misma estructura cambiando una palabra. Si te descubres escribiendo «Detectar y corregir…» y «Identificar y corregir…», borra las dos y empieza por lo que las separa.
- Cuando dos conceptos sean facetas de una misma tarea —la parte y el todo, el mecanismo y su uso, dos variantes del mismo algoritmo—, cada descripción enuncia EXACTAMENTE su faceta y da la otra por supuesta.
- Reparte el vocabulario: un término que sirve para varios conceptos de la lista no distingue a ninguno. Gasta las palabras específicas en el concepto al que de verdad pertenecen.

# OBJETIVO DE APRENDIZAJE, NO HERRAMIENTA (CRÍTICO)
Un ejercicio USA muchos conceptos y PRACTICA solo uno o dos. Cada descripción debe encajar con los ejercicios cuyo OBJETIVO es ese concepto —los que un alumno no podría resolver sin dominarlo— y NO con los que simplemente lo emplean de paso como vehículo para practicar otra cosa.

- Si una frase describiría igual de bien a un ejercicio donde el concepto es mero soporte, sobra.
- Escribe lo que el ejercicio EXIGE, no lo que el ejercicio contiene.
- Para conceptos paraguas o troncales con pocos detalles propios, prefiere una descripción MUY CORTA y sobria con lo único que los distingue. Mejor 1 frase específica que 4 genéricas.

# VOZ (CRÍTICO)
Cada descripción enuncia la tarea EN IMPERSONAL, empezando por un verbo en infinitivo: «Ordenar…», «Calcular…», «Reescribir…».
- PROHIBIDO nombrar a nadie: ni «el alumno», ni «el estudiante», ni «quien lo resuelve», ni «tú», ni «se te pide», ni «el ejercicio pide».
- PROHIBIDO hablar de ti o de este encargo: nada de «esta descripción», «el concepto que se describe», «en este caso».
- Ni una palabra de deliberación, ni alternativas, ni justificación: solo las descripciones, ya decididas.

# REGLAS DE FORMA
- 1-3 frases cada una, según haga falta para ser específica sin caer en lo genérico.
- Enunciado de tarea, no definición formal.
- Usa los términos, símbolos, sintaxis y construcciones que aparecerían de verdad en ejercicios de esta asignatura y este nivel. Lo que no aplique a esta materia, no lo uses.
- Idioma: el de instrucción que indique el contexto docente. Si no se desprende con claridad, el de los nombres de los conceptos.
- Texto plano sin ningún marcado: ni markdown, ni etiquetas, ni cercos (backticks, fences, comillas envolventes).

# SALIDA
Un único objeto JSON con esta forma exacta:
{{"descriptions": {{"<nombre exacto del concepto>": "<su descripción>"}}}}
- UNA entrada por cada concepto de la lista de abajo, ni una más ni una menos.
- Las claves son los nombres EXACTOS de la lista. No inventes, no renombres, no traduzcas ni corrijas la ortografía.
- Nada antes ni después, sin backticks, sin comentarios.

# CONCEPTOS DE «{domain}» QUE HAY QUE DESCRIBIR (con sus relaciones en el grafo)
{concepts_block}

JSON:"""


def concept_description_prompt(
    concept: str,
    domain: str,
    relations: dict[str, list[str]],
    siblings: dict[str, str],
    context_block: str,
    passages: list[dict] | None = None,
    name_documents: bool = False,
) -> str:
    context_section = f"\n# CONTEXTO DOCENTE\n{context_block}\n" if context_block.strip() else ""

    relations_block = ""
    relations_with_neighbors = {v: ns for v, ns in relations.items() if ns}
    if relations_with_neighbors:
        relations_lines = "\n".join(
            f"- {verbose}: {', '.join(neighbors)}."
            for verbose, neighbors in relations_with_neighbors.items()
        )
        relations_block = f"\n# RELACIONES EN EL GRAFO DEL CURRÍCULO\n{relations_lines}\n"

    siblings_block = ""
    if siblings:
        sibling_lines = []
        for name, text in siblings.items():
            written = " ".join((text or "").split())
            sibling_lines.append(f"- {name}: {written}" if written else f"- {name}")
        siblings_block = (
            "\n# OTROS CONCEPTOS DEL MISMO BLOQUE TEMÁTICO\n"
            "Tu descripción compite con estas: se comparan todas contra el mismo ejercicio y solo una debe encajar. "
            "Las que ya están escritas se muestran con su texto.\n"
            "Están aquí SOLO para que no te solapes con ellas. No copies su estructura, su voz ni sus fórmulas: "
            "si alguna incumple las reglas de forma de abajo, no la imites — las reglas mandan sobre el ejemplo.\n"
            + "\n".join(sibling_lines)
            + "\n"
        )

    # The corpus anchoring: the paragraphs of the theory material this concept came from.
    # Without them the model describes from memory and drags in the vocabulary of its own
    # training — that is how «Recursividad» ended up talking about automorphisms in a
    # first-year course. The document name is only given when the corpus has more than one:
    # with a single document it distinguishes nothing and only spends context.
    passages_block = ""
    if passages:
        cited = []
        for entry in passages:
            place = entry.get("location") or ""
            if name_documents:
                place = " · ".join(p for p in (entry.get("document") or "", place) if p)
            cited.append((f"[{place}]\n" if place else "") + (entry.get("text") or "").strip())
        passages_block = (
            "\n# DE DÓNDE SALE ESTE CONCEPTO (MATERIAL DE TEORÍA, LITERAL)\n"
            "Los fragmentos del temario en los que aparece. Son la única prueba de qué significa este concepto EN ESTA ASIGNATURA:\n"
            "- Toma de aquí el vocabulario, la notación y el nivel; lo que no esté aquí ni se deduzca del contexto docente, no lo inventes.\n"
            "- Si tu idea del concepto no coincide con lo que dice el material, manda el material.\n"
            "- No los cites ni los resumas: describe la TAREA que se practica con esto.\n\n"
            + "\n\n---\n\n".join(cited)
            + "\n"
        )

    return f"""\
Estás generando la descripción del concepto del currículo «{concept}», del bloque temático «{domain}».
{context_section}{passages_block}{relations_block}{siblings_block}
# OBJETIVO
Esta descripción es la superficie con la que se decidirá, para cada ejercicio del material docente, QUÉ CONCEPTO DEL CURRÍCULO PRACTICA ese ejercicio. Se compara semánticamente contra el enunciado de los ejercicios, así que debe LEER COMO el enunciado de un ejercicio de este concepto, o como su primera frase — no como la definición de manual del concepto.

Describe LA TAREA que se practica: lo observable que hay que hacer, no la teoría que hay detrás.

# OBJETIVO DE APRENDIZAJE, NO HERRAMIENTA (CRÍTICO)
Un ejercicio USA muchos conceptos y PRACTICA solo uno o dos. La descripción debe encajar con los ejercicios cuyo OBJETIVO es este concepto — aquellos que un alumno no podría resolver sin dominarlo — y NO con los que simplemente lo emplean de paso como vehículo para practicar otra cosa.

- Si una frase describiría igual de bien a un ejercicio donde este concepto es mero soporte, sobra.
- Escribe lo que el ejercicio EXIGE, no lo que el ejercicio contiene.

# DISTINTIVIDAD (CRÍTICO)
- La descripción debe encajar SOLO con ejercicios que practiquen este concepto en concreto, no con cualquier ejercicio de la materia.
- Evita el vocabulario transversal de la materia — palabras y giros que aparecerían naturalmente en ejercicios de muchos conceptos distintos. Identifica qué léxico es común a todo el temario (lo que usarías para describir la asignatura en general, o para describir cualquiera de los "otros conceptos del mismo bloque") y NO lo uses.
- No uses ejemplos concretos genéricos: placeholders típicos, datos de relleno o escenarios neutros que aparezcan en ejercicios de varios conceptos diferentes. Si das un ejemplo, que sea uno cuyo enunciado SOLO tendría sentido si el objetivo de aprendizaje fuera este.
- Para conceptos paraguas o troncales con pocos detalles propios, prefiere una descripción MUY CORTA y sobria que mencione únicamente lo que los distingue de los conceptos hermanos. Mejor 1 frase específica que 4 frases genéricas.
- Si lo que has escrito también describiría a un concepto hermano, REESCRÍBELO o RECÓRTALO hasta que no.
- Lee las descripciones ya escritas de los hermanos antes de responder. Si la tuya se solapa con alguna, el solapamiento es el error: quédate solo con lo que este concepto tiene y aquel no. Cuando dos hermanos son facetas de una misma tarea (la parte y el todo, el mecanismo y su uso), describe EXACTAMENTE tu faceta y da por supuesta la otra.

# VOZ (CRÍTICO)
La descripción enuncia la tarea EN IMPERSONAL, empezando por un verbo en infinitivo: «Ordenar…», «Calcular…», «Reescribir…».
- PROHIBIDO nombrar a nadie: ni «el alumno», ni «el estudiante», ni «quien lo resuelve», ni «tú», ni «se te pide», ni «el ejercicio pide».
- PROHIBIDO hablar de ti o de este encargo: nada de «esta descripción», «el concepto que se describe», «en este caso».
- Ni una palabra de deliberación, ni alternativas, ni justificación de lo que escribes: solo la descripción, ya decidida.

# REGLAS DE FORMA
- 1-4 frases, según haga falta para ser específico sin caer en lo genérico.
- Enunciado de tarea, no definición formal.
- Apóyate en el material de teoría, en el contexto docente y en las relaciones para inferir el registro, el nivel y el vocabulario de superficie de la materia — términos, símbolos, sintaxis, fórmulas, identificadores o construcciones propias que aparecerían de verdad en ejercicios de esa asignatura y ese nivel. Lo que no aplique a esta materia, no lo uses.
- Idioma: el de instrucción que indique el contexto docente. Si no se desprende con claridad, usa el mismo idioma de los nombres de los conceptos.
- Texto plano sin ningún tipo de marcado: ni markdown, ni etiquetas estructuradas, ni cercos (backticks, fences, comillas envolventes).

# SALIDA
Un único objeto JSON: {{"description": "…"}}. Nada antes, nada después.

JSON:"""
