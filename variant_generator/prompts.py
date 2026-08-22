# ── REPARACIÓN DE JSON ────────────────────────────────────────────────────────

def json_repair_prompt(broken_output: str, error_msg: str, shape: str = "array") -> str:
    return f"""\
La salida anterior no pudo parsearse como JSON válido o no cumple el schema requerido.

Tu tarea: produce un {shape} JSON corregido que (1) parsee como JSON válido, y (2) preserve la información original lo más fielmente posible.

# ERROR DEL INTENTO ANTERIOR
{error_msg}

# SALIDA ROTA A REPARAR
{broken_output}

# REGLAS
- Devuelve un único {shape} JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Escapa correctamente saltos de línea (`\\n`) y comillas internas (`\\"`) dentro de strings.
- Si la salida rota es irrecuperable, devuelve `{{}}`.

JSON:"""


# ── PREPARACIÓN DE CONTENIDO ──────────────────────────────────────────────────


# Appended by the page transcriber to the option a coloured/bold mark singles out on the
# page, and stripped again by the extractor. Two prompts, one convention: the mark has to
# be recognisable in the cached markdown a human may edit, and must never end up inside a
# field value.
CORRECT_ANSWER_MARK = "✔"

# What a page made of nothing but logos, headers and page numbers comes back as. Recognised
# by the reader and turned into an empty page, so it neither reaches a prompt nor looks
# like a transcription that silently failed.
EMPTY_PAGE_MARK = "[PÁGINA SIN CONTENIDO]"


def transcribe_page_prompt(page_number: int, page_count: int) -> str:
    return f"""\
Transcribe a Markdown la PÁGINA {page_number} de {page_count} de un documento de material docente. La tienes delante como imagen.

Tu trabajo es COPIAR lo que hay en la página, no interpretarlo. Un extractor posterior leerá tu transcripción creyendo que es el documento original, así que cualquier cosa que cambies se convierte en material docente falso.

# ORDEN DE LECTURA
Transcribe en el orden en que lo leería una persona. Cada enunciado debe quedar junto al código, la tabla, la imagen o las opciones que le pertenecen, en el sitio donde aparecen. Si la página tiene columnas, sigue la columna entera antes de pasar a la siguiente.

# FIDELIDAD — LO MÁS IMPORTANTE
- Copia CARÁCTER A CARÁCTER. `a -= 1` no es `a = a - 1`. `x = x - 1` no es `x = x + 1`. `range (0,8)` conserva su espacio. No normalices, no modernices, no arregles el estilo.
- NO resuelvas nada, NO completes lo que falte, NO corrijas errores del documento. Si el código tiene un fallo, el fallo es parte del ejercicio y se transcribe tal cual.
- Respeta la ortografía y los acentos del original.
- Si algo es ilegible, escribe `[ilegible]` en su lugar. Nunca adivines.

# CÓDIGO
El código va en bloques delimitados por ``` conservando EXACTAMENTE sus saltos de línea y su indentación. Es lo que peor sobrevive a una transcripción descuidada y lo que más daño hace: un fragmento de código con la indentación aplanada o un operador cambiado deja de ser el ejercicio que era.

# RESPUESTAS MARCADAS
Si una opción de respuesta está destacada visualmente respecto a las demás — color distinto, negrita, subrayado, recuadro, una marca al margen — añade ` {CORRECT_ANSWER_MARK}` al final de esa línea y nada más. Es la única marca que puedes añadir al texto. Si ninguna está destacada, no marques ninguna: no deduzcas cuál es la correcta.

# QUÉ OMITIR
Logotipos, escudos, cabeceras y pies institucionales, números de página y marcas de agua. Todo lo demás se transcribe, incluidas las tablas (en Markdown) y los enunciados administrativos que formen parte de un ejercicio.

# CONTINUIDAD
Transcribe solo lo que ves en ESTA página. Si un ejercicio empieza aquí y sigue en la siguiente, corta donde corta la página: no lo completes ni escribas notas sobre ello.

# SALIDA
Solo el Markdown de la página. Sin preámbulo, sin comentarios tuyos, sin ```markdown envolviendo el conjunto, sin decir «Aquí está la transcripción». Si la página no contiene nada más que elementos omitibles, responde exactamente `{EMPTY_PAGE_MARK}`.

Markdown:"""


def format_content_prompt(
    content: str,
    types_block: str,
    context_block: str = "",
    type_keys: list[str] | None = None,
) -> str:
    context_section = (
        f"\n# CONTEXTO DOCENTE DEL DOCUMENTO\n{context_block}\n" if context_block.strip() else ""
    )

    keys = ", ".join(f"`{k}`" for k in (type_keys or []))

    return f"""\
Extrae los ITEMS DE APRENDIZAJE de un fragmento markdown pre-segmentado de material docente.

Un item de aprendizaje es toda unidad que el material PLANTEA AL ALUMNO COMO TAREA: un ejercicio, un problema, una actividad, una pregunta, un supuesto práctico. Que venga acompañado de su solución no lo descalifica — sigue siendo un item, con su solución incluida.

NO son items de aprendizaje y no deben extraerse: la exposición teórica del temario, las explicaciones y definiciones, los ejemplos que el texto usa para ILUSTRAR una explicación sin pedir nada al alumno, los índices, los objetivos de la unidad, las rúbricas, la bibliografía y los avisos administrativos. Si el fragmento no plantea ninguna tarea, devuelve `[]`.

El input contiene uno o varios items. Si hay varios, vienen separados por líneas `---`. Cada bloque entre separadores (o el input completo si es un único bloque) representa exactamente UN item. Dentro de un bloque, todo lo que encuentres — sub-preguntas, apartados (a/b/c, i/ii/iii), bloques de código embebidos, instrucciones de seguimiento, párrafos explicativos, tablas, ejemplos — pertenece a ese único item: los apartados son una progresión de la misma tarea, no tareas distintas.

# PRIMERO CLASIFICA, DESPUÉS EXTRAE
La asignatura plantea sus tareas en varias MODALIDADES, y cada una tiene su propio esquema de campos. Para CADA item: decide primero a qué modalidad pertenece, y extrae después usando el esquema DE ESA modalidad y ninguno otro.

Cada objeto que devuelvas lleva una clave `item_type` con la clave de su modalidad ({keys}), MÁS los campos declarados por esa modalidad. Sin `item_type` el item se descarta.

Elige la modalidad por lo que el item PIDE AL ALUMNO, no por su tema ni por su dificultad. Si un item encaja en dos, quédate con aquella cuyos campos puedas rellenar del todo con lo que hay en el texto. Si no encaja en ninguna, NO lo extraigas: es preferible perder un item que inventarle una anatomía.

# MODALIDADES Y SUS ESQUEMAS
{types_block}

# REGLAS DE EXTRACCIÓN
- Copia los valores literalmente del texto fuente. No reescribas, no traduzcas, no resumas, no inventes contenido. Lo que se extrae es material docente real: alterarlo destruye justamente lo que lo hace útil como ejemplo.
- Si un campo admite null y el contenido no aparece en la fuente, ponlo a null. Nunca fabriques contenido para rellenar: un enunciado sin solución en el material es un item legítimo, uno con la solución inventada es material docente falso.
- No mezcles campos de dos modalidades en un mismo objeto: los únicos campos válidos son los de la modalidad que has declarado en `item_type`.
- El material puede venir de una transcripción que marca con `✔` la opción correcta de una pregunta cerrada. Esa marca NO es parte del texto: úsala para saber cuál es la respuesta correcta y quítala del valor que extraigas.
- Elimina marcadores de enumeración inicial (`1.`, `2)`, `Ejercicio 3:`, `Exercise 4.`, `Problema 5 -`, `Apartado 6:`, `Sección 7 –`, etc.) en los campos de texto. Los valores deben empezar con el primer carácter real del contenido, no con un número o etiqueta.
- Para strings multilínea (código, prosa con párrafos): escapa saltos como `\\n` y comillas internas como `\\"`.
- Respeta los constraints del schema (`minLength`, `maxLength`, `pattern`, etc.).

# REGLAS DE SALIDA
- Un único JSON array. Nada antes, nada después.
- Cada objeto lleva `item_type` más los campos de esa modalidad.
- Sin ```json, sin backticks, sin comentarios.
- Si el fragmento no plantea ninguna tarea al alumno, devuelve `[]`.
{context_section}
<<<CONTENT>>>
{content}
<<<END>>>

JSON:"""


# ── DESCRIPCIÓN DE CONCEPTOS ─────────────────────────────────────────────────


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


# ── ETIQUETADO DE CONCEPTOS ──────────────────────────────────────────────────


def tag_concepts_prompt(
    statement: str,
    candidates: str,
    relations: str = "",
    context_block: str = "",
) -> str:
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


# ── GENERACIÓN DE CONTENIDO ──────────────────────────────────────────────────


def generate_content_prompt(
    context_block: str,
    item_type_block: str,
    target_concepts_block: str,
    prerequisites_block: str,
    excluded_concepts_block: str,
    curriculum_block: str,
    rules_block: str,
    few_shot_block: str,
    already_generated: list[str],
    instance_template: str,
    fields_block: str,
    fixed_values_block: str,
    instructions: str = "",
) -> str:
    # Guarded, unlike before: a workspace has no context until one of the two builders has
    # synthesised one, and that is the state a fresh instance starts in. Unguarded, the
    # heading printed with nothing under it and the sentence below claimed a context that
    # was not there.
    context_section = (
        "\n# CONTEXTO DOCENTE\n"
        f"{context_block}\n"
        "Este contexto fija la materia, el nivel y el idioma de instrucción: ajusta a él el "
        "registro, la terminología y la extensión del ejercicio. Es información para ti, no "
        "texto que deba aparecer en el enunciado.\n"
        if context_block.strip()
        else ""
    )

    few_shot_section = (
        few_shot_block.strip()
        or "(Ningún ejemplo disponible: redacta el ejercicio de cero respetando las reglas anteriores.)"
    )

    already_block = ""
    if already_generated:
        existing_lines = "\n".join(f"- {s.strip()[:240]}" for s in already_generated)
        already_block = (
            "\n# ESCENARIOS YA USADOS EN ESTE LOTE\n"
            "Enunciados ya producidos para este mismo encargo. El tuyo se plantea en un ámbito "
            "distinto de todos ellos:\n"
            f"{existing_lines}\n"
        )

    prerequisites_section = ""
    if prerequisites_block.strip():
        prerequisites_section = (
            "\n# CONOCIMIENTO PREVIO: SE DA POR SABIDO\n"
            "El grafo del currículo sitúa estos conceptos antes del objetivo: el alumno ya los domina. "
            "Son el andamiaje con el que construir el ejercicio, no el reto. Apóyate en ellos con "
            "naturalidad; la dificultad viene del objetivo, y el ejercicio no puede reducirse a repasarlos:\n"
            f"{prerequisites_block}\n"
        )

    excluded_section = ""
    if excluded_concepts_block.strip():
        excluded_section = (
            "\n# TODAVÍA NO IMPARTIDO: PROHIBIDO\n"
            "El grafo del currículo sitúa estos conceptos después del objetivo: el alumno aún no los ha visto. "
            "No aparecen en el enunciado ni hacen falta para resolverlo; si tu primera idea los necesita, "
            "cámbiala. Si uno de ellos es inseparable del propio objetivo (el currículo puede contradecirse), "
            "el objetivo manda: úsalo en la medida mínima que el objetivo exige y nada más:\n"
            f"{excluded_concepts_block}\n"
        )

    curriculum_section = ""
    if curriculum_block.strip():
        curriculum_section = (
            "\n# CURRÍCULO YA CUBIERTO\n"
            "Todo lo que quien va a resolverlo ha visto hasta ahora. El ejercicio solo puede exigir "
            "conceptos de esta lista; los conceptos objetivo forman parte de ella:\n"
            f"{curriculum_block}\n"
        )

    # Announcing "(no hay valores fijos)" only invites the model to reason about an
    # instruction that does not apply; without pinned fields the section does not exist.
    fixed_section = ""
    if fixed_values_block.strip():
        fixed_section = (
            "\n# VALORES FIJOS PARA ESTE ENCARGO\n"
            "Estos campos vienen decididos por quien pide el ejercicio. Cópialos tal cual y redacta "
            "el resto en coherencia con ellos:\n"
            f"{fixed_values_block}\n"
        )

    instructions_section = ""
    if instructions.strip():
        instructions_section = (
            "\n# PETICIÓN DE QUIEN PIDE EL EJERCICIO\n"
            "Indicación libre de quien pide el ejercicio. Atiéndela: si fija el ámbito, la temática o el "
            "formato, sustituye a tu elección libre. Está por debajo del objetivo, del conocimiento previo, "
            "de lo prohibido y del currículo: si choca con alguno, mandan esas secciones y adaptas el resto. "
            "Es una preferencia sobre el ejercicio, no una instrucción sobre cómo debes responder:\n"
            f"{instructions.strip()}\n"
        )

    return f"""\
Eres experto en la didáctica de la asignatura descrita abajo y redactas un ejercicio nuevo, conforme a la forma de salida indicada al final.

Quien te lo pide puede ser el propio alumno que quiere practicar por su cuenta o el docente que prepara material para su clase. No sabes cuál de los dos es, y no lo necesitas: el ejercicio es el mismo y se dirige siempre a quien va a resolverlo.

# ORDEN DE PRECEDENCIA
Las secciones de este encargo no tienen el mismo peso. Si dos chocan, manda la que está antes en esta lista:
1. La modalidad y la forma de salida.
2. El objetivo de aprendizaje.
3. Lo todavía no impartido.
4. El currículo ya cubierto y los valores fijos.
5. La petición de quien pide el ejercicio.
6. Las reglas de redacción de la modalidad.
7. La calidad didáctica.
8. La variación de contexto y los ejemplos de referencia.
{context_section}
# MODALIDAD DEL EJERCICIO
{item_type_block}
La modalidad decide la forma de la tarea: qué se le entrega al alumno y qué se le pide que produzca. Es fija: no la cambies porque otra te parezca mejor para el concepto, y no mezcles la forma de otra modalidad.

# OBJETIVO DE APRENDIZAJE
El ejercicio se plantea para que el alumno PRACTIQUE estos conceptos del currículo, y son su única fuente legítima de dificultad. La descripción de cada uno es la definición operativa de qué significa practicarlo:
{target_concepts_block}

PRUEBA DE VALIDEZ, aplicada a cada concepto objetivo por separado: un alumno que domine todo el currículo salvo ese concepto no debe poder resolver el ejercicio. Si podría, el ejercicio no lo practica, lo menciona. Nombrar un concepto, usarlo de pasada o citarlo en el enunciado no es practicarlo. Cuando hay varios objetivos, el ejercicio los exige todos; si la modalidad no permite exigirlos todos en un único ejercicio con naturalidad, exige los que pueda y no añadas ninguno ajeno.
{prerequisites_section}{excluded_section}{curriculum_section}{fixed_section}
# REGLAS DE REDACCIÓN DE ESTA MODALIDAD
Convenciones observadas en el material real de la asignatura: cómo escribe esta asignatura esta modalidad. Son de obligado cumplimiento y describen la forma, no el contenido:
{rules_block}

# CALIDAD DIDÁCTICA
- Autosuficiencia: el enunciado se basta a sí mismo. Deja explícitos los datos de partida, su naturaleza y qué se espera como resultado. El alumno no necesita preguntar nada para empezar.
- Una sola lectura: si una frase admite dos interpretaciones que llevan a soluciones distintas, reescríbela. La ambigüedad evalúa comprensión lectora, no el objetivo de aprendizaje.
- Resoluble: existe una solución correcta alcanzable con el objetivo y el conocimiento previo, y con nada más.
- Sin carga ajena: la dificultad del ejercicio es la del objetivo, no la de descifrarlo. Fuera datos irrelevantes, rodeos narrativos, condiciones acumuladas y vocabulario rebuscado; todo lo que el alumno deba desenredar antes de pensar en el concepto es ruido que falsea la evaluación.
- Calibrado: ajusta alcance y exigencia al nivel del contexto docente y a lo que muestran los ejemplos de referencia. Ni un ejercicio trivial que no obligue a nada, ni uno que desborde lo que el objetivo permite.
- Sin voz de aula: el enunciado plantea la tarea y nada más. Sin saludos, presentaciones, ánimos ni comentarios tuyos sobre el propio ejercicio; sin referencias a la clase, al profesor, a una entrega o a una calificación. Quien lo lee puede estar practicando por su cuenta.

# VARIACIÓN DE CONTEXTO
El envoltorio, la situación concreta en la que se plantea la tarea, es tuyo y debe ser nuevo: elige un ámbito reconocible de la vida real que no aparezca en los ejemplos de referencia ni en los escenarios ya usados en este lote, y plantea el ejercicio en él. Cambiar el contexto y no la sustancia es lo que obliga al alumno a transferir el concepto en vez de reconocer un patrón memorizado. Lo que no cambia es la demanda cognitiva: el objetivo y su exigencia los fijan las secciones anteriores, y el ámbito elegido no añade datos ni reglas que haya que descifrar.
{instructions_section}
# EJEMPLOS DE REFERENCIA
Ejercicios reales del material docente de la asignatura, sobre conceptos próximos. Son referencia de forma, registro y extensión; su temática, su estructura literal y sus escenarios no se reutilizan.
{few_shot_section}
{already_block}
# CAMPOS DE LA SALIDA
Un objeto JSON con exactamente estas claves y ninguna otra. Un campo que clasifica el ejercicio (un nivel, una categoría) describe lo que has escrito, no lo decide de antemano: rellénalo al final, a partir del ejercicio terminado y de su criterio.
{fields_block}

Esqueleto exacto de la salida (rellena los valores):
{instance_template}

# ANTES DE RESPONDER, COMPRUEBA
- Cada concepto objetivo supera la prueba de validez: sin él, el ejercicio no se resuelve.
- Ningún concepto de lo todavía no impartido aparece ni hace falta, salvo el mínimo que el propio objetivo exige.
- El ámbito del enunciado no está en los ejemplos de referencia ni en los escenarios ya usados.
- El enunciado se basta a sí mismo, admite una sola lectura y no tiene voz de aula.
- Las claves son exactamente las del esqueleto y los valores fijos van copiados tal cual.

# FORMA DE LA SALIDA
- Un único objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Escapa saltos de línea (`\\n`) y comillas internas (`\\"`) dentro de los strings.

JSON:"""


# ── COMPARATIVE EVALUATION ────────────────────────────────────────────────────
#
# The two prompts of the reference arms of the Evaluation mode. Not the "best" ones: they
# are deliberately poor, because they measure what the system's additions contribute.
#
# What they DO carry, and why:
#   · the concept names — an ordinary user writes the topic;
#   · the teaching context — whoever asks for the exercise, student or teacher, knows
#     which subject and at what level they want it;
#   · the list of output keys — without it the arm returns prose and the comparison
#     would measure format instead of content, an artifact that invalidates the experiment;
#   · one register line — the commercial model opened the statement greeting and
#     commenting on the exercise. That is conversational format, not didactics: leaving it
#     would measure politeness instead of item quality, exactly the same artifact that
#     justifies the previous line. It says what NOT to put, not how to write the exercise.
# What they can NEVER carry: concept descriptions, prerequisites, posteriors, curriculum,
# or any didactic section of `generate_content_prompt`. All of that only exists thanks to
# the graph, which is precisely what is being measured.


# The one prompt that does NOT take the rendered block. It composes a sentence -- "Eres
# experto en X, a nivel de Y. Redáctalo en Z." -- because that is what a person who has
# never seen this system would type, and a paragraph of synthesised prose is not that. So
# the three canonical facts stay addressable by name in `ContentContext`, and this arm
# reads them and nothing else. Handing it the narrative would change a measured baseline
# and make old evaluation sessions incomparable.
def naive_generation_prompt(
    subject: str,
    educational_level: str,
    language_of_instruction: str,
    concepts: list[str],
    keys: list[str],
    fixed: dict[str, object] | None = None,
    instructions: str = "",
) -> str:
    subject = subject or "la asignatura"
    level = educational_level
    language = language_of_instruction

    header = f"Eres experto en {subject}"
    if level:
        header += f", a nivel de {level}"
    header += "."

    lines = [header, f"Escribe un ejercicio para practicar: {', '.join(concepts)}."]
    if language:
        lines.append(f"Redáctalo en {language}.")
    for name, value in (fixed or {}).items():
        lines.append(f"El campo {name} debe ser: {value}.")
    if instructions.strip():
        lines.append(instructions.strip())
    lines.append(f"Devuélvelo en JSON con las claves: {', '.join(keys)}.")
    lines.append(
        "El contenido de los campos es el ejercicio en sí: sin saludos, sin presentaciones, "
        "sin ánimos ni comentarios tuyos sobre el ejercicio, y sin nada de texto fuera del JSON."
    )
    return "\n".join(lines)


def rag_generation_prompt(
    naive_prompt: str,
    exemplars_block: str,
    rules_block: str,
    schema: str,
) -> str:
    exemplars_section = ""
    if exemplars_block.strip():
        exemplars_section = (
            "\n# EJEMPLOS DEL BANCO DE LA ASIGNATURA\n"
            "Ejercicios reales de la asignatura, recuperados por similitud con el encargo. "
            "Úsalos como referencia de forma y registro:\n"
            f"{exemplars_block}\n"
        )

    rules_section = ""
    if rules_block.strip():
        rules_section = f"\n# REGLAS DE REDACCIÓN DE LA ASIGNATURA\n{rules_block}\n"

    return f"""\
{naive_prompt}
{exemplars_section}{rules_section}
# SCHEMA DE SALIDA
{schema}

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON conforme al schema. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Las claves de nivel superior son exactamente las del schema.

JSON:"""


# ── THE SUBJECT'S CONTEXT ─────────────────────────────────────────────────────
#
# The context synthesis, shared by BOTH builders: the graph's calls it at the end of its
# curation with the syllabus blocks, and the profile's at the end of its own with the
# modalities. Each contributes what its artifact knows about the subject and neither sees
# what the other knows, so the call is always a MERGE: what was already written goes in
# and a text that incorporates it comes out.
#
# That is why what is legislated hardest here is preservation. The natural failure of a
# model given a text and new material is to rewrite the text; repeated on every rebuild,
# that paraphrases what a person wrote until it stops being theirs. What really stops the
# drift is the draft/curated pair — the curated one wins on read and this call never
# touches it —, but a text that respects what was already said is what makes the draft
# worth curating instead of rewriting whole.


def synthesize_content_context_prompt(
    current_block: str,
    evidence_block: str,
    source_label: str,
    max_chars: int,
) -> str:
    current_section = (
        "\n# CONTEXTO QUE YA EXISTE — PUNTO DE PARTIDA, NO BORRADOR A REESCRIBIR\n"
        f"{current_block}\n"
        if current_block.strip()
        else "\n# CONTEXTO QUE YA EXISTE\n(Ninguno todavía: lo estás escribiendo por primera vez.)\n"
    )
    return f"""\
Escribe, en prosa, QUÉ ASIGNATURA ES ESTA. El texto que produzcas se interpola en todos los prompts de un sistema que genera material de aprendizaje: es lo que fija la materia, el nivel de exigencia, el idioma y las convenciones propias de la asignatura para todo lo que ese sistema redacte después.

No describes un temario ni un programa docente. Describes el TERRENO: de qué va esto, a quién se dirige, en qué idioma se enseña y qué convenciones lo hacen reconocible.
{current_section}
# LO QUE APORTA {source_label}
{evidence_block}

# CÓMO FUSIONAR
- LO QUE YA ESTABA SE CONSERVA. Cada afirmación del contexto existente sigue en el texto final, y si puede seguir con sus mismas palabras, sigue con sus mismas palabras. Puede haberla escrito una persona a mano; parafrasearla sin necesidad es perderla poco a poco.
- SOLO AÑADES LO QUE EL MATERIAL NUEVO APORTA DE VERDAD. Si no aporta nada que no estuviera ya dicho, devuelve el contexto que ya había, tal cual. Es una respuesta correcta y frecuente.
- SI SE CONTRADICEN, MANDA LO QUE YA ESTABA. El material nuevo es una vista parcial de la asignatura; el contexto existente puede venir de una persona que la conoce entera.
- NO INVENTES. Ni universidad, ni curso académico, ni titulación, ni número de horas, ni bibliografía, ni nada que no esté en uno de los dos bloques de arriba. Ante la duda, omítelo.

# CÓMO DEBE SER EL TEXTO
- PROSA CONTINUA, en el idioma de instrucción de la asignatura. Una o dos frases seguidas; nada de listas, viñetas, encabezados ni pares clave-valor.
- COMO MUCHO {max_chars} CARACTERES. Es un techo duro y existe porque este texto se paga en cada llamada del sistema.
- NADA DE TEMARIO ENUMERADO. Puedes decir en una frase por dónde va la asignatura («cubre desde los tipos básicos hasta la recursividad»); no puedes listar los conceptos ni copiar los nombres de los bloques uno a uno. Para eso ya está el grafo, y quien lea esto lo tiene delante.
- SIN METACOMENTARIO. No hables del sistema, ni de este encargo, ni de lo que has hecho para escribirlo. El texto empieza describiendo la asignatura.
- SIN DESTINATARIO. No te dirijas a nadie: ni «tú», ni «el alumno debe», ni «ten en cuenta que». Es una descripción, no una instrucción.

# LOS TRES DATOS APARTE
Además de la prosa, extrae tres datos sueltos, porque otra parte del sistema los necesita por separado y no puede leer el párrafo:
- `subject`: el nombre de la asignatura o materia.
- `educational_level`: la etapa o el curso («primer curso de grado», «segundo de bachillerato»).
- `language_of_instruction`: el idioma en que se enseña.
Cada uno, cadena vacía si no se deduce con seguridad de los bloques de arriba. Deben ser COHERENTES con la prosa: lo que digan tiene que estar también dicho en ella.

# REGLAS DE SALIDA
- Un único objeto JSON con exactamente las claves `narrative`, `subject`, `educational_level` y `language_of_instruction`. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- `narrative` en UNA SOLA LÍNEA: escapa los saltos (`\\n`) y las comillas internas (`\\"`).

JSON:"""


# ── PERFIL DE EJEMPLARES ───────────────────────────────────────────────────────


EXEMPLARS_PROFILE_FIELD_NAMING = """\
- CLAVES EN ESPAÑOL, SIN TILDES (INNEGOCIABLE): los nombres de campo — las claves del objeto `fields` — van en ESPAÑOL, en snake_case y en ASCII puro; cada uno debe casar con `^[a-z][a-z0-9_]*$`. Español sí, tildes no: se convierten en identificadores de código, así que escribe `solucion` y no «solución», `explicacion` y no «explicación», `disenio` o `diseno` y nunca «diseño». Sin ñ, sin espacios, sin mayúsculas, sin guiones.
- VOCABULARIO CANÓNICO: los nombres deben ser estables entre asignaturas distintas, para que un ejercicio de programación y uno de física se describan con las mismas claves. Si un campo desempeña uno de estos roles, usa EXACTAMENTE ese nombre en vez de inventar un sinónimo:
  · el texto principal que plantea al alumno la tarea, el problema o la pregunta → `enunciado`
  · la respuesta, resolución o resultado esperado → `solucion`
  · el grado de dificultad o exigencia → `nivel_dificultad`
  · el título o nombre corto del ejercicio → `titulo`
  · las alternativas de una pregunta cerrada → `opciones`
  · cuál de las alternativas es la correcta → `respuesta_correcta`
  · el material de partida que se le entrega ya escrito al alumno (código con un fallo, plantilla a completar, texto a corregir, datos de entrada) → `material_base`
  · la explicación didáctica o justificación de la respuesta → `explicacion`
  Inventa un nombre nuevo SOLO si el rol del campo no aparece en esta lista; entonces aplícale las mismas reglas. No añadas sufijos que describan el soporte concreto de esta muestra: `solucion`, no `codigo_solucion`.
- NOMBRES RESERVADOS, prohibidos como campo: `item_type`, `id`, `source`, `concepts`, `primary_concept`. Los usa el propio sistema.
- NADA DE CAMPOS DE MODALIDAD: no declares un campo `tipo`, `tipo_item`, `modalidad`, `formato` ni equivalente. La modalidad del ejercicio ES la clave de su entrada en `item_types`; un campo así la duplicaría.
- VOCABULARIO CANÓNICO: los nombres deben ser estables entre asignaturas distintas, para que un ejercicio de programación y uno de física se describan con las mismas claves. Si un campo desempeña uno de estos roles, usa EXACTAMENTE ese nombre en vez de inventar un sinónimo:
  · el texto principal que plantea al alumno la tarea, el problema o la pregunta → `statement`
  · la respuesta, resolución o resultado esperado → `solution`
  · el grado de dificultad o exigencia → `difficulty_level`
  · el título o nombre corto del ejercicio → `title`
  · las alternativas de una pregunta cerrada → `options`
  · la explicación didáctica o justificación de la respuesta → `explanation`
  · la modalidad o formato del ejercicio → `item_type`
  Inventa un nombre nuevo SOLO si el rol del campo no aparece en esta lista; entonces aplícale las mismas reglas. No añadas sufijos que describan el soporte concreto de esta muestra: `statement`, no `instruction_text`; `solution`, no `solution_code`.\
"""


EXEMPLARS_PROFILE_SCHEMA_GRAMMAR = """\
`schema` es SIEMPRE un objeto JSON. Nunca una lista, nunca una cadena suelta. TODAS sus claves van DENTRO de ese objeto; ninguna como hermana de `schema`. Vocabulario permitido, y ninguno más:
- `"type"`: uno de `"string"`, `"integer"`, `"number"`, `"boolean"`, `"array"`, `"object"`.
- `"type"` como LISTA de esos mismos nombres, para valores que admiten ausencia: {"type": ["string", "null"]}. Dentro de `type` todo son NOMBRES DE TIPO entrecomillados, `"null"` incluido.
- con `"type": "array"`, la clave `"items"` va DENTRO del schema: {"type": "array", "items": {"type": "string"}}. Una lista que puede faltar combina ambas formas: {"type": ["array", "null"], "items": {"type": "string"}}.
- `"enum"`: lista no vacía de VALORES literales permitidos (no nombres de tipo), para campos categóricos: {"enum": ["básico", "intermedio", "avanzado"]}. SOLO aquí, y solo si el campo admite ausencia según la POLÍTICA DE NULOS, puede aparecer el literal JSON `null` como un valor más de la lista.
- restricciones opcionales, dentro del mismo objeto: `"minLength"`, `"maxLength"`, `"minimum"`, `"maximum"`, `"default"`.

Formas VÁLIDAS de `schema` — no hay ninguna más:
  {"type": "string"}
  {"type": ["string", "null"]}
  {"type": "array", "items": {"type": "string"}}
  {"enum": [1, 2, 3, 4]}

Formas INVÁLIDAS (errores reales ya cometidos; no los repitas):
  ["string", "null"]                    → falta el envoltorio: es {"type": ["string", "null"]}
  {"type": "array"} + `items` hermana   → `items` va dentro del objeto `schema`
  {"type": "str"} / "text" / "list"     → esos nombres de tipo no existen\
"""


def scan_item_types_prompt(content: str, location: str = "", excerpt_chars: int = 400) -> str:
    where = f"\nFragmento procedente de: {location}\n" if location else ""
    return f"""\
Analiza un FRAGMENTO de material docente en bruto (ejercicios, problemas, actividades, preguntas) e inventaria las MODALIDADES de ejercicio que aparecen en él.

Una modalidad es una FORMA de plantear la tarea al alumno, definida por la anatomía del ejercicio: qué piezas de información lo componen. Ejemplos de modalidades distintas: una pregunta cerrada con alternativas; un encargo de escribir un programa desde cero; un fragmento de código con un fallo que hay que localizar y corregir; una plantilla con huecos que completar; un trozo de código cuya salida hay que predecir.

Este fragmento es SOLO UNA PARTE del material: no intentes describir la asignatura entera ni adivinar modalidades que no estén aquí. Inventaria lo que VES en este fragmento, y nada más. Otro paso posterior reunirá los inventarios de todos los fragmentos.
{where}
# QUÉ CUENTA COMO EJERCICIO
Cuenta toda unidad que el material PLANTEA AL ALUMNO COMO TAREA. No cuentan: la exposición teórica, las explicaciones y definiciones, los ejemplos que ilustran una explicación sin pedir nada, los índices, los objetivos de la unidad, las rúbricas ni la bibliografía. Si el fragmento no plantea ninguna tarea, devuelve `{{"types": []}}`.

# DOS MODALIDADES SON LA MISMA SI SE RELLENAN IGUAL
La prueba, aplícala antes de separar nada: ¿se rellenarían las MISMAS piezas de información al redactar uno y otro? Si sí, es UNA modalidad, por muy distinto que sea el rótulo del documento.
- «Ejercicio propuesto» y «Ejercicio resuelto» son la MISMA modalidad: que uno traiga la solución y el otro no es un campo vacío, no una modalidad nueva.
- «Ejercicio básico» y «Ejercicio avanzado» son la MISMA modalidad: la dificultad es un campo, no una modalidad.
- «Ejercicio 3.1» y «Ejercicio 7.2» son la misma modalidad: la numeración y el tema no la cambian.
- Una pregunta con alternativas y un encargo de programar SÍ son modalidades distintas: la primera necesita una lista de opciones y una respuesta correcta; el segundo, un enunciado y código.
Ante la duda, AGRUPA. Separar de más fragmenta el material en modalidades anecdóticas; agrupar de más se corrige después.

# QUÉ DEBES PRODUCIR
Un único objeto JSON:

{{
  "types": [
    {{
      "key": "<clave en espanol, snake_case, sin tildes>",
      "label": "<nombre legible de la modalidad, en el idioma del material>",
      "signals": "<como se reconoce en el documento: rotulos, encabezados, estructura visible>",
      "fields": ["<nombre_de_campo>", "..."],
      "excerpt": "<hasta {excerpt_chars} caracteres literales del ejemplar mas representativo>"
    }}
  ]
}}

- `key`: en español, `^[a-z][a-z0-9_]*$`, sin tildes ni ñ. Nombra la MODALIDAD, no el tema: `pregunta_test`, `escritura_codigo`, `correccion_error`, `completar_codigo`, `prediccion_salida`, `problema_teorico`.
- `fields`: las piezas que componen ESTA modalidad, con los nombres canónicos de abajo. Solo las que el fragmento muestra de verdad.
- `excerpt`: copia LITERAL, recortada a {excerpt_chars} caracteres, del ejemplar que mejor representa la modalidad. Es lo que verá el paso siguiente para redactar las instrucciones de extracción, así que elige uno completo y típico, no el más raro. Escapa saltos (`\\n`) y comillas (`\\"`).

# NOMBRES DE CAMPO
{EXEMPLARS_PROFILE_FIELD_NAMING}

# REGLAS DE SALIDA
- Un único objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Si el fragmento no plantea ninguna tarea al alumno, devuelve `{{"types": []}}`.

<<<FRAGMENTO>>>
{content}
<<<FIN>>>

JSON:"""


def consolidate_exemplars_profile_prompt(findings: str, max_types: int) -> str:
    return f"""\
Has recibido el INVENTARIO de modalidades de ejercicio que un escaneo previo encontró, fragmento a fragmento, en todo el material docente en bruto de una asignatura. Consolídalo en el PERFIL DE EJEMPLARES definitivo.

El perfil es la ÚNICA pieza que instancia el sistema para una asignatura concreta: el mismo motor genera ejercicios de programación, problemas de física, preguntas de test o supuestos prácticos, pero siempre material de aprendizaje. Declara, de forma abstracta, la anatomía de cada modalidad de ejercicio de esta asignatura: qué campos la componen, de qué tipo son, cómo se extraen de un documento y cómo se redactaría uno nuevo.

El inventario viene de fragmentos analizados por separado, así que TRAE DUPLICADOS: la misma modalidad aparecerá con claves distintas, con conjuntos de campos que se solapan y con etiquetas parecidas. Unificarlos es tu trabajo principal.

# QUÉ DEBES PRODUCIR
Un único objeto JSON con EXACTAMENTE estas claves de nivel superior:

{{
  "item_types": {{
    "<clave_de_modalidad>": {{
      "label": "<nombre legible>",
      "description": "<que es esta modalidad y como se reconoce>",
      "primary_field": "<nombre de uno de sus campos>",
      "embed_fields": ["<primary_field>", "<otro campo que el alumno RECIBE>"],
      "general_generation_rules": ["<regla>", "..."],
      "fields": {{
        "<nombre_de_campo>": {{
          "schema": {{ "type": "string" }},
          "description": "...",
          "guidance": {{ "extraction": "..." }}
        }}
      }}
    }}
  }}
}}

# QUÉ NO DEBES DECLARAR
Nada sobre la asignatura en sí: ni la materia, ni el nivel educativo, ni el idioma, ni convenciones generales de la carrera. Eso se escribe aparte, en prosa, en otro paso del sistema. Aquí describes ÚNICAMENTE la anatomía de las modalidades. No añadas claves de nivel superior: `item_types` es la única.

# item_types — CUÁNTAS MODALIDADES
- FUSIONA SIN MIEDO. Dos entradas del inventario son la MISMA modalidad si se rellenan las mismas piezas al redactarlas. Que una traiga solución y otra no, que una sea básica y otra avanzada, que estén en unidades distintas: nada de eso separa. Al fusionar, quédate con la clave más clara y con la UNIÓN de sus campos (los que falten en una variante son campos que admiten `null`, ver POLÍTICA DE NULOS).
- SEPARA SOLO CUANDO CAMBIA LA ANATOMÍA. Una modalidad distinta necesita campos que la otra no tiene sentido que tenga, o una forma de redactarse claramente distinta. Prueba: si las dos comparten `fields` y sus `general_generation_rules` saldrían casi iguales, es una sola.
- DESCARTA LO ANECDÓTICO. Una modalidad que aparece una vez en todo el corpus y que encaja razonablemente dentro de otra, va dentro de la otra. Solo sobrevive por su cuenta la que el material usa de verdad como formato propio.
- COMO MUCHO {max_types} modalidades. Si te salen más, es que estás separando por tema o por dificultad en vez de por anatomía: vuelve a fusionar. Lo habitual son 1-3.
- Ordénalas de más frecuente a menos: la primera es la que el sistema usa por defecto.

Para cada modalidad:
- `label`: su nombre legible, en el idioma del material («Pregunta tipo test», «Corrección de errores»).
- `description`: qué es y cómo se reconoce. Lo lee tanto el extractor —para decidir a qué modalidad pertenece cada ejercicio del documento— como el generador. Sé discriminante: describe lo que la distingue de las demás modalidades del perfil, no lo que tienen en común.
- `general_generation_rules`: cómo se redacta un ejercicio NUEVO de esta modalidad. Es la parte más importante de lo que produces y tiene sección propia más abajo — léela antes de escribirlas.

# fields — CÓMO SE LLAMAN
{EXEMPLARS_PROFILE_FIELD_NAMING}
- COHERENCIA ENTRE MODALIDADES: si dos modalidades tienen un campo con el mismo papel, debe llamarse IGUAL en las dos (`enunciado` en todas, no `enunciado` en una y `pregunta` en otra).

# fields — CUÁLES INCLUIR
Un campo por cada pieza de información ESENCIAL que compone un ejercicio de esa modalidad.

- MENOS ES MÁS: incluye el conjunto MÍNIMO de campos que capture por completo un ejercicio. Cada campo debe ganarse su sitio: NO añadas campos especulativos, redundantes, derivables de otros ni presentes solo de forma anecdótica. Al mismo tiempo, NO omitas nada esencial para representar o redactar el ejercicio (como mínimo, el que porta la carga semántica principal). Ante la duda entre añadir un campo marginal o dejarlo fuera, déjalo fuera. Lo habitual son 3-5 campos por modalidad.
- PRUEBA DE DERIVABILIDAD (aplícala a CADA campo antes de incluirlo): si su valor puede calcularse a partir de los demás campos sin volver a mirar el documento, NO es un campo — se deduce, y sobra. Descarta en particular: banderas que solo indican si otro campo tiene valor o está vacío (`is_solved`, `tiene_solucion`: eso ya lo dice que `solucion` sea null); contadores, longitudes o tamaños de otro campo; y campos cuyo valor sea una reformulación de otro. Si al describir un campo necesitas mencionar otro campo para definirlo, es señal casi segura de que es derivable.
- NADA DE CONCEPTOS NI TEMAS: no declares campos de conceptos, temas, materia o etiquetas temáticas (`temas`, `conceptos`, `palabras_clave`…). Qué concepto del currículo practica cada ejercicio lo anota el sistema aguas abajo contra un grafo de conocimiento, y un campo así se solaparía con esa anotación. Lo que sitúe a la asignatura entera (materia, nivel educativo, idioma) no va en `fields` ni en ningún otro sitio de este perfil.
- COBERTURA MÍNIMA: el perfil debe bastar para (a) representar el ejercicio, (b) recuperarlo semánticamente y (c) redactar uno nuevo PARAMETRIZADO. En la práctica eso casi siempre exige: el enunciado que porta la carga semántica (el `primary_field`, obligatorio); la solución esperada, cuando el material la trae o la admite; y al menos un campo CLASIFICATORIO que se pueda fijar como parámetro al pedir un ejercicio nuevo (dificultad, nivel…). Si la muestra no etiqueta ese eje clasificatorio pero es deducible observando el ejercicio, decláralo igualmente y define el criterio (ver POLÍTICA DE NULOS).

Para cada campo:
- `schema`: la forma del valor.
{EXEMPLARS_PROFILE_SCHEMA_GRAMMAR}
- `description`: la NATURALEZA intrínseca del campo (qué representa), en el idioma de instrucción de la asignatura.
- `guidance.extraction`: cómo EXTRAER este campo de un documento fuente. **Redáctala con más detalle y precisión que el resto de textos**: alimenta un proceso de extracción posterior que debe ser exacto y determinista, así que sé concreto y accionable, y apóyate en los fragmentos literales del inventario. Cubre, cuando apliquen: qué copiar y si va LITERAL o normalizado; los LÍMITES con los campos vecinos (qué pertenece a este campo y qué NO, para que no se solapen); los marcadores o encabezados concretos del documento que lo delimitan (p. ej. "Solución:", "Ejercicios propuestos"); qué EXCLUIR (etiquetas de enumeración, cabeceras de sección, artefactos de página); y, solo en campos que admitan ausencia según la POLÍTICA DE NULOS, cuándo el campo va a null. Aplica a todo campo que pueda localizarse en el material.
- `guidance.generation`: **NO la escribas. Nunca.** Existe en el formato, pero es un campo que rellena a mano quien administra la asignatura cuando un campo concreto necesita un matiz que las reglas no cubren. Tú deja en `guidance` únicamente `extraction`. Lo que sepas sobre cómo se REDACTA esta modalidad va entero en `general_generation_rules`.

# POLÍTICA DE NULOS — `null` ES EL ÚLTIMO RECURSO
Un campo admite `null` SOLO cuando el contenido que representa PUEDE NO EXISTIR en un ejercicio de esa modalidad (p. ej. la solución de un ejercicio que se plantea sin resolver). Que el documento no lo ETIQUETE explícitamente NO es motivo para admitir `null`: es motivo para definir un criterio que permita DEDUCIRLO del propio contenido.

Por tanto, para todo campo CLASIFICATORIO (nivel, categoría…):
- NO lo declares opcional por defecto. Si su valor es deducible observando el ejercicio, el campo NO lleva `null`.
- Su `description` debe incluir un CRITERIO INTERNO DE CLASIFICACIÓN propio de la asignatura: enumera cada valor posible junto a las SEÑALES OBSERVABLES que lo identifican (qué construcciones, qué complejidad, qué exigencia o qué conocimientos previos supone el ejercicio). El criterio debe cubrir TODO el material, de modo que cualquier ejercicio pueda clasificarse sin excepción.
- Su `guidance.extraction` debe decir: si el documento trae una etiqueta explícita, se usa esa; si NO la trae, se aplica al contenido del ejercicio el criterio definido en `description`. NUNCA "si no hay etiqueta, null".

# general_generation_rules — CÓMO ESCRIBE ESTA ASIGNATURA (LA PARTE QUE MÁS IMPORTA)
Es lo ÚNICO que el perfil le dice al generador sobre cómo se redacta un ejercicio de esta modalidad. Aquí no hay una segunda oportunidad campo a campo: lo que no esté en estas reglas, el generador no lo sabe. Dedícale más atención que a ninguna otra parte del perfil.

Escríbelas mirando los `excerpt` del inventario y preguntándote qué tienen en común TODOS los ejemplares de esta modalidad. Una regla es una CONVENCIÓN OBSERVADA en este material, no una opinión tuya sobre didáctica.

- CADA REGLA DEBE SER COMPROBABLE. Tiene que poder leerse un ejercicio ya escrito y decir si la cumple o no. «El enunciado debe ser claro» no es comprobable y no es una regla; «el enunciado debe especificar la entrada, la salida y el comportamiento esperado» sí lo es.
- NOMBRA EL CAMPO al que se aplica cuando la regla sea de un campo concreto («la solución debe…», «el enunciado debe…»). No hay guía por campo que lo diga en tu lugar, así que la regla tiene que decirlo ella.
- CUBRE, cuando el material los muestre de forma consistente: qué debe contener obligatoriamente cada campo redactado; la NOTACIÓN y las convenciones de formato propias de la asignatura (cómo se documenta, qué encabezados, qué unidades, qué símbolos); la EXTENSIÓN y el alcance típicos de un ejemplar; y las relaciones de COHERENCIA entre campos (que la solución responda exactamente a lo que pide el enunciado, que el material de partida y la solución encajen).
- NADA DE DIDÁCTICA GENÉRICA. «Debe fomentar el pensamiento crítico», «debe ser motivador», «adecuar la dificultad al nivel»: de todo eso ya se ocupa el generador, que sabe de didáctica y no sabe de esta asignatura. Tú aportas lo segundo. Si una regla valdría igual para cualquier asignatura del mundo, sobra.
- NADA DE CONTENIDO. No fijes el tema, el ámbito ni los conceptos de los ejercicios: eso lo decide cada encargo contra el grafo del currículo. Las reglas hablan de la FORMA.
- SOLO DE ESTA MODALIDAD. Una regla que solo tiene sentido aquí (exigir docstring y bloque de prueba) va SOLO aquí. Si es cierta de todas las modalidades por igual, es que describe la asignatura entera y no aporta nada en ninguna.
- CANTIDAD: entre 3 y 8. Menos de 3 casi siempre significa que no has mirado los ejemplares; más de 8, que estás desmenuzando una regla en sus consecuencias o colando didáctica genérica.

# primary_field
Uno por modalidad. El nombre del campo que porta la CARGA SEMÁNTICA principal del ejercicio: el enunciado, el texto que plantea la tarea al alumno. Aguas abajo es lo que se compara contra el grafo del currículo para decidir qué concepto practica cada ejercicio, así que debe ser el campo que se lee para saber de qué va el ejercicio. Debe ser una de las claves de los `fields` de ESA modalidad.

# embed_fields
La lista de campos que, JUNTOS, se leen para decidir qué concepto del currículo practica el ejercicio. Es una lista porque en algunas modalidades el enunciado por sí solo no dice de qué va el ejercicio: en «¿qué imprime el siguiente código?» el enunciado es una fórmula fija y el concepto está en el CÓDIGO QUE SE LE ENTREGA al alumno.

- Empieza SIEMPRE por el `primary_field`, y añade después solo los campos que el alumno RECIBE junto al enunciado y sin los cuales el ejercicio no se entiende: el material de partida, el fragmento de código a analizar, las opciones de una pregunta de test.
- NUNCA incluyas la SOLUCIÓN ni la explicación de la respuesta. Es la respuesta, no el ejercicio: al medirlo, incluirla EMPEORÓ el acierto. Tampoco incluyas campos clasificatorios (dificultad, nivel): no aportan concepto y añaden ruido idéntico en todos los ejercicios.
- Prueba: tapa el campo. Si al leer lo que queda ya no puede decirse qué concepto se practica, el campo va en la lista. Si sigue pudiendo decirse, se queda fuera.
- Si el enunciado se basta solo, `embed_fields` es exactamente `["<primary_field>"]`.

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Los nombres de campo (claves de `fields`) y las claves de `item_types` SIEMPRE en español, snake_case, sin tildes ni ñ. El resto de texto de cara al humano (`label`, `description`, `guidance`, `general_generation_rules`) en el idioma del material.
- Incluye solo los campos ESENCIALES: menos es más, pero sin dejar fuera nada imprescindible. Ninguno derivable de otro. `null` únicamente donde el contenido pueda no existir.
- Cada valor de texto en UNA SOLA LÍNEA: sin saltos de línea reales, sin backticks ni bloques de código dentro de los strings. Escapa saltos (`\\n`) y comillas internas (`\\"`).
- ANTES DE RESPONDER, verifica las seis cosas que más fallan: (1) el valor de cada `schema` es un OBJETO `{{...}}`, nunca una lista; (2) cada clave de `fields` y cada clave de `item_types` casa con `^[a-z][a-z0-9_]*$`; (3) el `primary_field` de cada modalidad es exactamente una de las claves de SUS `fields`; (4) `embed_fields` empieza por el `primary_field`, solo nombra campos de SUS `fields` y no incluye la solución; (5) no hay dos modalidades que se rellenen igual; (6) NINGÚN `guidance` lleva la clave `generation`, y cada modalidad trae entre 3 y 8 `general_generation_rules` comprobables.

<<<INVENTARIO>>>
{findings}
<<<FIN>>>

JSON:"""


def repair_exemplars_profile_prompt(profile: str, error_msg: str) -> str:
    return f"""\
El siguiente PERFIL DE EJEMPLARES parsea como JSON válido pero no cumple el formato exigido. Corrígelo.

# ERROR DE VALIDACIÓN
{error_msg}

# PERFIL A CORREGIR
{profile}

# FORMATO DE `schema` — causa habitual del error
{EXEMPLARS_PROFILE_SCHEMA_GRAMMAR}

# NOMBRES DE CAMPO
{EXEMPLARS_PROFILE_FIELD_NAMING}

# REGLAS
- Conserva el contenido original (`label`, `description`, `guidance`, reglas) tal cual; corrige SOLO lo que incumple el formato. Si renombras un campo, renómbralo también donde se le referencie.
- Clave de nivel superior exactamente una: `item_types`. Nada más a ese nivel. Si el perfil trae un `content_context`, DÉJALO donde está: es de una versión anterior y otro paso lo migra; no lo borres ni lo edites.
- `item_types` es un objeto NO VACÍO. Cada clave casa con `^[a-z][a-z0-9_]*$` y su valor declara al menos `primary_field` y `fields`, y opcionalmente `label`, `description` y `general_generation_rules`.
- El `primary_field` de cada modalidad debe ser una de las claves de SUS PROPIOS `fields`.
- `embed_fields`, si está, es una lista no vacía y sin repeticiones que EMPIEZA por el `primary_field` de esa modalidad y solo nombra claves de SUS PROPIOS `fields`.
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después. Sin backticks, sin comentarios, sin explicaciones.

JSON:"""


# ── GRAFO DE CONOCIMIENTO ─────────────────────────────────────────────────────
#
# The JSON keys these prompts draw — `concepts`, `relations`, `merges`, `canonical`,
# `aliases`, `drop`, `domains`, `non_taggable` — stay English: they are the grammar
# `schemas.py` pins and what the parsers read. Only the prose is Spanish. ORIGEN and
# DESTINO name the two slots of a triple and must match `relations.py`.

_KG_LANGUAGE_RULE = """\
# IDIOMA
Escribe el nombre de cada concepto EN EL MISMO IDIOMA que el material de origen. No lo traduzcas, no lo normalices a otro idioma, no lo transliteres. Conserva la redacción, los acentos y las mayúsculas de la terminología de la asignatura.
Las claves de los tipos de relación que se listan abajo son IDENTIFICADORES FIJOS, no palabras del texto: emítelas exactamente como están escritas, sea cual sea el idioma del material."""


def _kg_type_preference_rule(schema) -> str:
    if schema.fallback is None:
        return (
            "- Emite una relación solo cuando uno de los tipos de arriba se aplique con "
            "claridad. Si ninguno lo hace, no emitas la relación."
        )
    specific = ", ".join(f"`{key}`" for key in schema.specific_keys())
    return (
        f"- Prefiere el tipo ESPECÍFICO ({specific}) siempre que su lectura sea claramente "
        f"cierta; reserva `{schema.fallback}` para asociaciones reales que no encajen en "
        f"ningún otro. No fuerces un tipo específico ante la duda, pero tampoco uses "
        f"`{schema.fallback}` como cajón de sastre por defecto."
    )


_KG_DEFINITION_RULE = """\
# UNA DEFINICIÓN POR CONCEPTO
Cada concepto lleva una DEFINICIÓN de UNA frase, tomada de cómo lo explica el propio fragmento: qué es, en los términos de la materia. Es lo que permitirá, más adelante, distinguir dos nombres parecidos y decidir qué se enseña antes de qué, así que tiene que nombrar la idea y no el ejemplo.
- Una sola frase, de 10 a 25 palabras, impersonal (sin «el alumno», sin «se aprende a»).
- Dice QUÉ ES, no para qué se usa en el ejercicio ni con qué herramienta se hace.
- Si el fragmento solo menciona el concepto sin explicarlo, una definición mínima basta; no inventes detalle que el texto no da."""


_KG_EXTRACT_OUTPUT = """\
# SALIDA
Un único objeto JSON exactamente con esta forma:
{
  "concepts": [{"name": "<concepto>", "definition": "<una frase>"}, "..."],
  "relations": [["<origen>", "<tipo>", "<destino>"], "..."]
}
- El `<tipo>` es uno de los identificadores listados arriba. Nada más.
- Todo origen y todo destino de `relations` se escribe con el nombre EXACTO del concepto."""


def extract_typed_graph_prompt(source_text: str, schema, location: str = "") -> str:
    location_block = ""
    if location:
        location_block = (
            "\n# DÓNDE SE SITÚA ESTE FRAGMENTO EN EL MATERIAL\n"
            f"{location}\n"
            "Es la ruta de encabezados de la sección de la que se ha tomado el fragmento. "
            "Úsala para distinguir de QUÉ trata la sección frente a lo que solo menciona de "
            "pasada, y para nombrar los conceptos como los nombra esta parte del temario — "
            "los fragmentos vecinos de esta misma sección se están leyendo con este mismo "
            "encabezado, así que sus nombres tienen que salir idénticos a los tuyos.\n"
        )

    return f"""\
Extrae un GRAFO DE CONOCIMIENTO de un fragmento de material docente de CUALQUIER asignatura. Identifica los CONCEPTOS de la materia y las RELACIONES TIPADAS entre ellos, directamente en el esquema que se indica abajo.
{location_block}

# QUÉ CUENTA COMO CONCEPTO VÁLIDO
Un concepto NOMBRA una idea de la materia: un término que podría ser una entrada de un glosario o de un índice (una cosa, técnica, categoría, estructura, fenómeno o entidad con nombre propio). NO es una frase que describa o predique algo.
- Prueba del glosario: si NO lo pondrías como entrada en un índice de la materia, NO es un concepto.
- NO extraigas: metadatos del documento (títulos de sección, bibliografía, licencias, autores), escenarios incidentales de los ejemplos (objetos, personajes o situaciones concretas que solo ilustran), ni fragmentos que se lean como parte de una oración (empiezan por un verbo, contienen un verbo conjugado, o expresan una condición o una acción).

# CANON DE NOMBRADO (CRÍTICO)
Este fragmento es uno de cientos extraídos por separado del mismo corpus, y los resultados se fusionan POR NOMBRE. Dos fragmentos que nombren la misma idea de forma distinta producen dos conceptos que no se reconciliarán nunca, así que no nombres lo que este fragmento dice por casualidad — nombra lo que diría el índice de la materia.
- SINGULAR siempre, aunque el fragmento hable en plural.
- Forma SUSTANTIVA, nunca el adjetivo ni la cualidad: nombra la cosa, no su propiedad.
- Sin artículos, sin determinantes, sin posesivos.
- Sin ningún matiz tomado del ejemplo, del ejercicio o de la herramienta de turno: nombra el concepto y para ahí.
- Conserva la redacción que el propio material docente usa para la idea cuando la tiene; no la traduzcas, no la modernices, no desarrolles una abreviatura que el material mantiene corta.
- La misma idea debe salir con el MISMO nombre siempre, aparezca en el fragmento que aparezca.

{_KG_DEFINITION_RULE}

{_KG_LANGUAGE_RULE}

# TIPOS DE RELACIÓN (respeta la dirección ORIGEN → DESTINO)
Cada relación es una terna [origen, tipo, destino]. La dirección importa: elige el orden que hace cierta la lectura enunciada.
{schema.catalog_block()}

# REGLAS DE RELACIÓN
- El origen y el destino deben ser DISTINTOS, y ambos deben aparecer en tu lista `concepts`. Está prohibido relacionar un concepto consigo mismo.
{_kg_type_preference_rule(schema)}
- Extrae solo las relaciones SOSTENIDAS por el texto del fragmento, no por conocimiento externo.
- Sé exhaustivo con las relaciones: cuando el fragmento explique un concepto apoyándose en otro, eso es una relación que enunciar, aunque el texto no la formule como tal. Dos conceptos de tu lista que el fragmento trate juntos y sin ninguna relación entre ellos es, casi siempre, una relación que falta.

{_KG_EXTRACT_OUTPUT}
- Si el fragmento no da ningún concepto extraíble, devuelve {{"concepts": [], "relations": []}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# FRAGMENTO
{source_text}

JSON:"""


# The second reading of a chunk. Shown the inventory the first one wrote, it is asked only
# for what is missing — the «gleaning» pass of GraphRAG and LightRAG — and its answer is
# merged into the first, never replacing it.
def glean_typed_graph_prompt(
    source_text: str,
    schema,
    location: str,
    concepts: list[str],
    definitions: dict[str, str],
    relations: list[list[str]],
) -> str:
    location_line = f"Sección: {location}\n" if location else ""
    found_concepts = "\n".join(
        f"- {name} — {definitions[name]}" if definitions.get(name) else f"- {name}"
        for name in concepts
    )
    found_relations = (
        "\n".join(f'- ["{s}", "{k}", "{t}"]' for s, k, t in relations) or "- (ninguna)"
    )
    return f"""\
Un primer lector extrajo de este fragmento de material docente los conceptos y las relaciones tipadas que se listan abajo. Una primera lectura SIEMPRE se queda corta: nombra lo evidente, enuncia pocas relaciones y cierra.

Tu tarea: una SEGUNDA lectura del mismo fragmento que devuelva SOLO lo que falta — conceptos de la materia que el primer lector no nombró y, sobre todo, RELACIONES que el texto sostiene entre conceptos ya nombrados y que no aparecen en la lista.
{location_line}
# QUÉ BUSCAR
- Relaciones entre dos conceptos YA LISTADOS que el fragmento trata juntos: cuando explica uno apoyándose en el otro, cuando uno es un caso o una parte del otro, cuando el texto los presenta en secuencia. Recorre la lista de conceptos de dos en dos y pregúntate si el texto los relaciona.
- Conceptos que el fragmento explica (no que solo menciona de pasada) y que no están en la lista. Aplica la prueba del glosario: si no sería una entrada de un índice de la materia, no es un concepto.
- Nombra los conceptos nuevos con el canon del primer lector: SINGULAR, forma sustantiva, sin artículos, sin matices del ejemplo, y con la misma redacción que el propio material usa.
- Reutiliza EXACTAMENTE los nombres ya listados cuando una relación los mencione. No los reescribas, no los corrijas, no los traduzcas.

{_KG_DEFINITION_RULE}

{_KG_LANGUAGE_RULE}

# TIPOS DE RELACIÓN (respeta la dirección ORIGEN → DESTINO)
{schema.catalog_block()}

# REGLAS DE RELACIÓN
- El origen y el destino deben ser DISTINTOS y ambos deben estar en la lista ya conocida o en tu lista `concepts`.
{_kg_type_preference_rule(schema)}
- Extrae solo las relaciones SOSTENIDAS por el texto del fragmento, no por conocimiento externo.
- NO repitas nada de lo ya listado: ni conceptos ni relaciones. Solo lo nuevo.

{_KG_EXTRACT_OUTPUT}
- En `concepts` van SOLO los conceptos nuevos; los ya conocidos pueden usarse en `relations` sin volver a listarlos.
- Si de verdad no falta nada, devuelve {{"concepts": [], "relations": []}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# CONCEPTOS YA EXTRAÍDOS
{found_concepts}

# RELACIONES YA EXTRAÍDAS
{found_relations}

# FRAGMENTO
{source_text}

JSON:"""


_KG_TEACHING_ORDER_RULE = """\
# EL ORDEN DE ENSEÑANZA ES LO QUE IMPORTA
La extracción fragmento a fragmento solo ve una dependencia cuando dos conceptos se explican de una misma vez, que es justo cuando el material NO necesita enunciarla. El orden del temario falta, por tanto, casi por completo, y recuperarlo es la razón principal de que exista este paso.
- Recorre los conceptos preguntándote, para cada uno: ¿qué debe entender YA un alumno antes de que esto pueda enseñarse? Cada respuesta que esté a su vez en la lista es una relación que proponer.
- Una dependencia es real aunque los dos conceptos no hayan aparecido nunca juntos: que estén lejos el uno del otro en el material es evidencia A FAVOR de proponerla aquí, no en contra.
- La mayoría de los conceptos de una materia se apoyan en algo. Un concepto sin nada delante debería ser la excepción — los puntos de partida de verdad —, no la norma.
- No encadenes lo que ya está implícito: enuncia la dependencia DIRECTA, no toda la ascendencia. Si A se apoya en B y B en C, no relaciones además A con C.
- Ser cauto no sale gratis aquí: una dependencia que dejes fuera es una que ningún paso posterior puede recuperar.
- Prefiere que AMBOS extremos sean cosas que se le enseñan a un alumno y de las que se le podría examinar. La extracción recogió también herramientas, notación, llamadas de biblioteca y vocabulario del documento; un orden colgado de eso describe el material y no el temario, y nada aguas abajo puede usarlo. Cuando una dependencia sea real pero uno de los extremos sea un término así, busca el concepto enseñado que hay detrás y relaciona ese."""


_KG_MATERIAL_ORDER_RULE = """\
# EL ORDEN DE LA LISTA ES EL ORDEN DEL MATERIAL
Los conceptos se listan en el ORDEN EN QUE EL MATERIAL LOS INTRODUCE, de principio a fin del corpus. Quien escribió el material ya decidió un orden de enseñanza, y ese orden es la mejor evidencia que tienes:
- Un concepto se apoya, casi siempre, en conceptos que van ANTES que él en la lista. Para cada uno, mira hacia arriba y pregúntate cuáles de los anteriores tiene que saber ya un alumno.
- Proponer que un concepto se apoye en otro que va DESPUÉS en la lista es afirmar que el material lo enseña en el orden equivocado. Puede ser cierto — un manual a veces adelanta una consecuencia —, pero exige que la dependencia sea inequívoca; ante la duda, respeta el orden del material.
- La distancia en la lista no es un obstáculo: lo primero del corpus es el cimiento de casi todo lo que viene después, y esas dependencias largas son justo las que faltan.
- Cada concepto lleva, cuando se conoce, una definición de una frase tomada del material. Juzga la dependencia sobre la definición, no sobre el parecido de los nombres."""


def link_domain_relations_prompt(domain: str, nodes_block: str, schema) -> str:
    return f"""\
Se te dan los conceptos de UN bloque temático, «{domain}», de un grafo de conocimiento construido a partir del material docente de una sola asignatura. Cada concepto se lista con las relaciones que ya se conocen de él, como evidencia.

Tu tarea: propón las RELACIONES TIPADAS que FALTAN entre los conceptos de este bloque — sobre todo el orden en que hay que enseñarlos.

{_KG_LANGUAGE_RULE}

# TIPOS DE RELACIÓN (respeta la dirección ORIGEN → DESTINO)
{schema.catalog_block()}

# REGLAS
- El origen y el destino deben ser DISTINTOS y ambos deben aparecer LITERALMENTE en la lista de abajo. No inventes conceptos, no reescribas sus nombres y no relaciones un concepto consigo mismo.
- NO repitas una relación que ya se muestre como evidencia. Solo lo que falta.
{_kg_type_preference_rule(schema)}

{_KG_TEACHING_ORDER_RULE}

{_KG_MATERIAL_ORDER_RULE}

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "relations": [["<origen>", "<tipo>", "<destino>"], "..."]
}}
- El `<tipo>` es uno de: {schema.key_list()}.
- Si no falta nada, devuelve {{"relations": []}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# CONCEPTOS DE «{domain}», EN EL ORDEN DEL MATERIAL (con su definición y las relaciones ya conocidas)
{nodes_block}

JSON:"""


def link_cross_domain_relations_prompt(domains_block: str, schema) -> str:
    return f"""\
Se te dan los conceptos de un grafo de conocimiento construido a partir del material docente de una sola asignatura, agrupados en los BLOQUES TEMÁTICOS del temario. Las relaciones dentro de cada bloque ya se han propuesto.

Tu tarea: propón SOLO las RELACIONES TIPADAS que CRUZAN de un bloque a otro — el armazón que ordena el temario en su conjunto y que ninguna lectura de un solo bloque podría revelar.

{_KG_LANGUAGE_RULE}

# TIPOS DE RELACIÓN (respeta la dirección ORIGEN → DESTINO)
{schema.catalog_block()}

# REGLAS
- El origen y el destino deben pertenecer a BLOQUES DISTINTOS. Una relación entre dos conceptos del mismo bloque se descartará: no es para lo que sirve este paso.
- Ambos deben aparecer LITERALMENTE en las listas de abajo. No inventes conceptos y no reescribas sus nombres.
{_kg_type_preference_rule(schema)}

{_KG_TEACHING_ORDER_RULE}

{_KG_MATERIAL_ORDER_RULE}
- Trabaja bloque a bloque: para cada uno, pregúntate en qué conceptos de los bloques ANTERIORES se apoya. Los bloques también vienen en el orden en que el material los presenta, y dentro de cada bloque sus conceptos siguen ese mismo orden.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "relations": [["<origen>", "<tipo>", "<destino>"], "..."]
}}
- El `<tipo>` es uno de: {schema.key_list()}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# BLOQUES TEMÁTICOS Y SUS CONCEPTOS, EN EL ORDEN DEL MATERIAL (cada concepto con su definición)
{domains_block}

JSON:"""


def merge_candidate_groups_prompt(groups_block: str) -> str:
    return f"""\
Se te dan GRUPOS PEQUEÑOS de nombres de nodo de un grafo de conocimiento extraído automáticamente de un corpus de material docente, cada nombre con sus relaciones salientes como evidencia. La extracción fue fragmento a fragmento y cada fragmento nombró las cosas con sus propias palabras, así que la MISMA idea llega varias veces vestida con otra gramática. Los grupos se formaron SOLO por parecido de nombre, que es una sospecha, no un veredicto: muchos grupos contienen nombres que simplemente se parecen y hay que dejar en paz.

Tu tarea: dentro de CADA grupo, y nunca entre grupos, decide qué nombres son EL MISMO CONCEPTO y deben fundirse en uno.

# LA PRUEBA DE FUSIÓN: UNA ENTRADA DE GLOSARIO, UN CONCEPTO
- ¿Un índice de la materia daría a estos nombres UNA entrada o DOS? Si una, fúndelos, por distinta que sea su gramática.
- Funde a través de la forma gramatical: el adjetivo, el sustantivo y la cualidad de la misma idea son un solo concepto; también lo son el singular, el plural y el sintagma nominal en plural; y también un término y ese mismo término con el objeto al que se aplica pegado detrás.
- Funde un término con su propia definición usada como nombre: cuando un nombre enuncia la idea y otro desarrolla esa misma idea como una frase más larga, son un solo concepto.
- NO fundas dos ideas de las que un alumno podría examinarse por separado, aunque aparezcan siempre juntas: un mecanismo y la técnica que lo usa siguen aparte, y también una parte y el todo al que pertenece, y también un término general y una de sus clases concretas.
- NO fundas dos nombres solo porque pertenezcan al mismo tema, estén relacionados o aparezcan a menudo juntos. Compartir una palabra no es evidencia.
- Usa las relaciones como evidencia: nombres con relaciones claramente distintas suelen ser conceptos distintos.
- Cuando un nombre lleve detrás de « — » una definición tomada del material, juzga sobre las definiciones antes que sobre los nombres: dos definiciones de la misma idea son un concepto, dos definiciones distintas son dos, por mucho que los nombres se parezcan.
- Fundir de más cuesta más que fundir de menos: un concepto perdido en una fusión no se recupera después. Cuando las dos lecturas sean igual de defendibles, déjalos aparte.

# NOMBRE CANÓNICO
- El canónico DEBE ser uno de los nombres de su propio grupo, copiado exactamente. No inventes nombres, no los traduzcas, no corrijas su ortografía.
- Prefiere la forma más corta que siga nombrando la idea por completo, y la que esté escrita como sustantivo.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "merges": [{{"canonical": "<nombre>", "aliases": ["<nombre>", "..."]}}, "..."]
}}
- Una entrada por cada conjunto de nombres que SEAN el mismo concepto. Los nombres que no se funden con nada simplemente no aparecen.
- Nunca pongas nombres de dos grupos distintos en la misma entrada.
- Si no se funde nada en ningún grupo, devuelve {{"merges": []}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# GRUPOS
{groups_block}

JSON:"""


def filter_graph_nodes_prompt(nodes_block: str) -> str:
    return f"""\
Se te da parte de los NODOS de un grafo de conocimiento extraído automáticamente de un corpus de material docente de una sola asignatura, cada uno con sus relaciones salientes como evidencia. La extracción es ruidosa: junto a los conceptos de la materia recogió metadatos, escenarios incidentales y fragmentos de oración.

Tu tarea: lista los nodos que NO nombran un concepto de la materia y hay que eliminar. Todo lo que no listes se conserva.

# QUÉ CUENTA COMO NODO VÁLIDO
Un nodo válido NOMBRA un concepto de la materia: un término que podría ser una entrada de un glosario o de un índice (una cosa, idea, técnica, categoría, estructura, fenómeno o entidad con nombre propio). NO es una frase que describa, explique o predique algo.

# ELIMINA
- Metadatos del documento: títulos de sección, bibliografía, licencias, autores, elementos de
  maquetación.
- Fragmentos que no son sintagmas nominales: cualquier cosa que empiece por un verbo, lleve un
  verbo conjugado, o enuncie una condición o una acción.
- Letras sueltas, símbolos aislados y valores desnudos.
- Los objetos, personajes o escenarios de los ejemplos ilustrativos, que pertenecen al ejemplo
  y no a la materia.

Juzga únicamente si la cadena NOMBRA algo. Si lo que nombra sirve como ETIQUETA de ejercicios
es otra pregunta, que se hace más tarde y con el perfil de ejemplares delante; no la respondas
aquí. Un término paraguas, una cualidad transversal o una etapa genérica del trabajo NOMBRAN
algo, así que se quedan.

# CONSERVA
- No elimines un término por ser corto, elemental, genérico o poco frecuente. La rareza no es evidencia de ruido aquí, y si un concepto sirve como ETIQUETA lo decide mucho más tarde otro paso — esa no es tu pregunta.
- Cuando un nodo nombre algo de la materia, por poco que sea, consérvalo.

# ANTE LA DUDA
- Cuando un nodo lleve detrás de « — » una definición tomada del material, léela: un nombre torpe con una definición que enuncia una idea de la materia es un concepto y se queda.
- Prueba del glosario: si NO lo pondrías como entrada en un índice de la materia, elimínalo.
- Ante un FRAGMENTO, elimina incluso en la duda. Ante un CONCEPTO, conserva incluso en la duda.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "drop": {{"<nodo>": "<por qué no nombra un concepto, 10 palabras máximo>"}}
}}
- Las claves son nombres EXACTOS de la lista de abajo. No inventes, no renombres, no traduzcas ni corrijas la ortografía.
- Juzga solo los nodos listados aquí. Si todos son conceptos, devuelve {{"drop": {{}}}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# NODOS
{nodes_block}

JSON:"""


def curate_graph_domains_prompt(nodes_block: str, documents_block: str = "") -> str:
    sources_block = ""
    sources_rule = ""
    if documents_block:
        sources_block = (
            "\n# LOS DOCUMENTOS DE LOS QUE SE COMPONE EL CORPUS\n"
            f"{documents_block}\n"
            "Cada documento se lista bajo un código con el título que él mismo se da; los "
            "títulos que repiten casi todos los documentos (la cabecera de la asignatura, los "
            "nombres de sección fijos) ya se han quitado, así que lo que queda es lo que "
            "distingue un documento de otro. Cada concepto de abajo lleva entre paréntesis los "
            "códigos de los documentos de los que se extrajo.\n"
        )
        sources_rule = (
            "\n- PARTE DE LOS TÍTULOS DE LOS DOCUMENTOS: el material docente ya está organizado "
            "por temas, así que un título que nombra un bloque temático es un nombre de dominio "
            "válido, y los conceptos extraídos de ese documento son sus miembros naturales. Son "
            "un PUNTO DE PARTIDA, no una restricción: funde varios documentos en un dominio, "
            "parte un documento que cubra varios bloques, reescribe un título que describa un "
            "documento en vez de un tema, e ignora cualquier título que no nombre tema alguno."
        )

    return f"""\
Se te dan los CONCEPTOS ya limpios de un grafo de conocimiento. Proceden de un solo corpus de material docente de una asignatura.

Tu tarea: NOMBRA los DOMINIOS temáticos de los que se compone la materia. NO estás colocando los conceptos — cada uno de ellos se asignará después a uno de tus dominios, por lotes pequeños. Nombra los bloques y nada más.
{sources_block}
# DOMINIOS
- Un dominio es un bloque temático de la materia (al estilo de los temas o unidades principales de un temario), no una etiqueta de grano fino.
- Propón POCOS dominios (como orientación, entre 3 y 8), cada uno cubriendo una masa razonable de los conceptos de abajo.{sources_rule}
- ENTRE TODOS DEBEN CUBRIR LA LISTA ENTERA: léela hasta el final y comprueba que cada concepto tendría un dominio evidente al que ir. Un concepto que ninguno de tus dominios recibiría significa que falta un bloque.
- NADA DE CAJÓN DE SASTRE: está PROHIBIDO crear un dominio genérico de descarte del tipo «Otros», «Varios», «Miscelánea» o «Sin clasificar». Todo concepto tiene un tema, y un dominio que no nombra ningún tema no puede recibir ninguno.

# NOMBRES
- Los NOMBRES DE LOS DOMINIOS los escribes tú: cortos y descriptivos, EN EL MISMO IDIOMA que los conceptos.
- No repitas un nombre, y no escribas dos nombres para el mismo bloque.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "domains": ["<Nombre de dominio>", "..."]
}}
- Solo los nombres de los dominios: un puñado de cadenas, nada más.
- NO listes los conceptos y NO escribas qué concepto va dónde. Esa es una pregunta posterior, y todo lo que escribas aquí sobre ella se descarta.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# CONCEPTOS
{nodes_block}

JSON:"""


# Asked to partition several hundred concepts in one turn, the model reliably forgets a
# fifth of them however loudly the prompt insists on completeness — 84 of 399 in the
# reference build. Rather than insisting harder, the leftovers are handed back as their own,
# much smaller question, with the domains already decided so this pass cannot invent more.
def assign_leftover_concepts_prompt(domains_block: str, nodes_block: str) -> str:
    return f"""\
Los conceptos de un grafo de conocimiento construido a partir del material docente de una sola asignatura ya se han agrupado en dominios temáticos. Los conceptos de abajo QUEDARON FUERA de esa agrupación — no porque estén mal, sino porque se pasaron por alto.

Tu tarea: coloca CADA concepto de abajo en UNO de los dominios EXISTENTES.

# REGLAS
- Los nombres de los dominios son FIJOS. Úsalos exactamente como están escritos. NO crees dominios nuevos, NO los renombres, NO dejes fuera ningún concepto.
- Cada concepto de abajo debe aparecer exactamente una vez en la salida.
- Asigna por tema y por la evidencia de las relaciones: el dominio que ya contiene los conceptos con los que este se relaciona es casi siempre el correcto. La definición que acompaña a cada concepto, detrás de « — », dice de qué trata cuando el nombre no basta.
- No hay «otros» ni «sin clasificar»: si un concepto parece no encajar en ninguno, elige aquel con el que sea MENOS ajeno.
- Usa los nombres EXACTOS de la entrada. No inventes, no renombres, no traduzcas ni corrijas la ortografía.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "domains": {{"<nombre de dominio existente>": ["<concepto>", "..."]}}
}}
- Solo hace falta que aparezcan los dominios que reciban al menos un concepto.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# DOMINIOS EXISTENTES Y LO QUE YA CONTIENEN
{domains_block}

# CONCEPTOS A COLOCAR (con las relaciones ya conocidas)
{nodes_block}

JSON:"""


def review_taggable_concepts_prompt(
    domain: str,
    domains_block: str,
    nodes_block: str,
    context_block: str,
    modalities_block: str,
    samples_block: str = "",
) -> str:
    context_section = f"\n# CONTEXTO DOCENTE\n{context_block}\n" if context_block.strip() else ""
    samples_section = (
        "\n# EJERCICIOS REALES DEL MATERIAL DE ESTA ASIGNATURA (cómo es aquí un ejercicio)\n"
        f"{samples_block}\n"
        if samples_block.strip()
        else ""
    )
    return f"""\
Estás revisando UN dominio temático de un grafo de conocimiento construido a partir de un corpus de material docente de una sola asignatura. El grafo existe para ETIQUETAR ejercicios (problemas, tareas de evaluación), y una etiqueta responde exactamente a una pregunta: ¿qué hace PRACTICAR ese ejercicio a quien lo resuelve?

Tu tarea: decide cuáles de los conceptos listados abajo son INÚTILES COMO ETIQUETA y hay que excluir del etiquetado. Todo lo que no listes sigue sirviendo como etiqueta.
{context_section}
# QUÉ ES UN EJERCICIO EN ESTA INSTANCIA
Esta asignatura plantea sus tareas en estas modalidades, y toda etiqueta que conserves se usará
para etiquetar ejercicios DE ESTAS FORMAS y de ninguna otra. Un concepto sobre el que ningún
ejercicio de estas modalidades podría tratar jamás es inútil como etiqueta aquí, por respetable
que sea como término.
{modalities_block}
{samples_section}
# LA PRUEBA: ¿DISCRIMINA?
Para cada concepto, en este orden:
1. ¿Podría un ejercicio tener ESTE concepto como objetivo — uno que un alumno que domina todo lo demás salvo este NO pudiera resolver? Si no, exclúyelo.
2. ¿Podría ponerse esta misma etiqueta, sin mentir, a ejercicios que practican cosas claramente distintas de partes distintas del temario? Si sí, exclúyelo.
Una etiqueta que encaja en casi todo no dice nada de nada.

# EXCLUYE
- Uno de cualesquiera dos conceptos de este dominio que acabarían etiquetando LOS MISMOS ejercicios — aquellos que ningún ejercicio podría distinguir porque lo que practica uno practica el otro. Conserva el que un docente escribiría en el examen, excluye el otro. (Un concepto excluido sigue en el grafo a través de sus relaciones.)
- La asignatura, el curso o la disciplina en sí, sus unidades, y los términos paraguas que solo nombran una parte del temario.
- Actividades o etapas genéricas del trabajo: escribir, ejecutar, diseñar, analizar, probar, documentar, mantener, resolver y similares.
- Cualidades y virtudes transversales: calidad, eficiencia como virtud, legibilidad, corrección, utilidad — salvo que el corpus la trate como un objeto técnico con contenido y criterios propios.
- Vocabulario del MATERIAL en vez de la materia: concepto, técnica, notación, ejemplo, resumen, lectura recomendada, introducción, principio, final, títulos de sección.
- Lenguajes, herramientas, plataformas, bibliotecas, estándares y sus nombres.
- Un término padre cuyos hijos específicos están también en la lista y que no aporta nada más allá de ellos.
- Letras y símbolos sueltos, valores aislados, y los objetos, personajes o escenarios de los ejemplos ilustrativos.

# CONSERVA
- Cualquier técnica, estructura, mecanismo, operación, regla o fenómeno específico de la materia, AUNQUE sea elemental: elemental no es lo mismo que genérico. Un ejercicio puede tratar sobre ello.
- Todo aquello que se le puede pedir a un alumno que aplique, construya, trace, compare, elija entre varias opciones o corrija.
- No excluyas un concepto por ser corto, frecuente o prerrequisito de muchos otros: lo que importa es si un ejercicio puede TRATAR SOBRE él, no cuántas veces se usa como herramienta.

# ANTE LA DUDA, EXCLUYE
Un concepto excluido sigue en el grafo y sigue haciendo su trabajo a través de sus relaciones (prerrequisitos, jerarquía, composición); simplemente no se usa nunca como etiqueta. Un concepto conservado que no discrimina contamina el etiquetado de todo el corpus.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "non_taggable": {{"<concepto>": "<por qué no discrimina, 12 palabras máximo>"}}
}}
- Las claves son nombres EXACTOS de la lista de abajo. No inventes, no renombres, no traduzcas ni corrijas la ortografía.
- Juzga solo los conceptos de este dominio. Si todos discriminan, devuelve {{"non_taggable": {{}}}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# DOMINIOS DE LA MATERIA (contexto: esto es el temario entero)
{domains_block}

# CONCEPTOS DEL DOMINIO «{domain}» (con sus relaciones salientes como evidencia)
{nodes_block}

JSON:"""
