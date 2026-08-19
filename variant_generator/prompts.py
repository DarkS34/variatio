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
    context: dict | None = None,
    type_keys: list[str] | None = None,
) -> str:
    context_block = ""
    if context:
        context_lines = "\n".join(f"- {k}: {v}" for k, v in context.items())
        context_block = f"\n# CONTEXTO DOCENTE DEL DOCUMENTO\n{context_lines}\n"

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
{context_block}
<<<CONTENT>>>
{content}
<<<END>>>

JSON:"""


# ── DESCRIPCIÓN DE CONCEPTOS ─────────────────────────────────────────────────


def concept_description_prompt(
    concept: str,
    domain: str,
    relations: dict[str, list[str]],
    siblings: dict[str, str],
    context: dict,
    passages: list[dict] | None = None,
    name_documents: bool = False,
) -> str:
    context_block = ""
    if context:
        context_lines = "\n".join(f"- {key}: {value}" for key, value in context.items())
        context_block = f"\n# CONTEXTO DOCENTE\n{context_lines}\n"

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

    # El anclaje al corpus: los párrafos del material de teoría de donde salió este
    # concepto. Sin ellos el modelo describe de memoria y arrastra el vocabulario de su
    # propio entrenamiento — así es como «Recursividad» acabó hablando de automorfismos en
    # un curso de primero. El nombre del documento solo se dice cuando el corpus tiene más
    # de uno: con un único documento no distingue nada y solo gasta contexto.
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
{context_block}{passages_block}{relations_block}{siblings_block}
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
    context: dict | None = None,
) -> str:
    context_block = ""
    if context:
        context_lines = "\n".join(f"- {key}: {value}" for key, value in context.items())
        context_block = f"\n# CONTEXTO DOCENTE\n{context_lines}\n"

    relations_block = ""
    if relations.strip():
        relations_block = (
            "\n# RELACIONES ENTRE LOS CANDIDATOS\n"
            "Relaciones del grafo del currículo entre los propios candidatos. Dicen cómo se ordenan estos conceptos en la secuencia de aprendizaje; úsalas para elegir el NIVEL DE ESPECIFICIDAD correcto:\n"
            f"{relations}\n"
        )

    return f"""\
Estás catalogando el banco de ejercicios de una asignatura. Para el ejercicio de abajo, decide QUÉ CONCEPTOS DEL CURRÍCULO hace practicar a quien lo resuelve.
{context_block}
# CONCEPTOS CANDIDATOS
Ordenados de mayor a menor relevancia semántica respecto al enunciado. Bajo cada nombre está la descripción del concepto: describe la tarea que se le plantea al alumno cuando lo practica. Juzga por la descripción, no por el nombre.
{candidates}
{relations_block}
# DISTINCIÓN CENTRAL: PRACTICAR NO ES USAR
Todo ejercicio USA muchos conceptos y PRACTICA solo uno o dos. Aquí se etiqueta lo que PRACTICA.
- Un concepto se PRACTICA si el ejercicio existe para ponerlo a prueba: es lo que el alumno aprende o demuestra al resolverlo.
- Un concepto se USA cuando aparece como vehículo, soporte o notación de la tarea, pero se da por dominado y el ejercicio no lo evalúa.
- PRUEBA DECISIVA: imagina un alumno que domina todo lo demás salvo ese concepto. ¿Resolvería el ejercicio igualmente? Si la respuesta es sí, el concepto se usa, no se practica: queda FUERA.

# ESQUEMA DE SALIDA
{{
  "concepts": ["Concepto A", "Concepto B"],
  "primary_concept": "Concepto A"
}}

# REGLAS
- Usa ÚNICAMENTE conceptos de la lista de candidatos. No inventes ni parafrasees nombres.
- `primary_concept`: el OBJETIVO DE APRENDIZAJE del ejercicio — aquello que el ejercicio existe para poner a prueba, lo que se evaluaría con él. Debe aparecer también en `concepts`.
- `concepts`: el primario más los demás conceptos que el ejercicio ponga a prueba de verdad. Rara vez pasan de tres; una lista larga casi siempre significa que has colado herramientas.
- ESPECIFICIDAD: entre dos candidatos donde uno es un tipo de otro, o parte de otro, el primario es el MÁS ESPECÍFICO que el ejercicio practique de verdad. El general entra en `concepts` solo si el ejercicio lo evalúa además por sí mismo.
- SECUENCIA DE APRENDIZAJE: si un candidato es prerrequisito de otro y ambos aparecen, lo normal es que el ejercicio practique el POSTERIOR y se apoye en el prerrequisito como base ya sabida. Etiqueta el prerrequisito solo si el enunciado lo pone a prueba de forma explícita.
- El orden de los candidatos es una pista, no una respuesta: el primero no tiene por qué ser el primario.
- Si el ejercicio practica claramente un solo concepto, `concepts` tendrá un único elemento.
- Si NINGÚN candidato es aquello que el ejercicio practica de forma central, devuelve {{"concepts": [], "primary_concept": null}}. Usa esta opción con criterio: solo cuando ningún candidato describa el objetivo real del ejercicio, no ante mera incertidumbre.
- Responde SOLO con el JSON. Sin texto antes ni después, sin backticks, sin comentarios.

# EJERCICIO A ETIQUETAR
{statement}

JSON:"""


# ── GENERACIÓN DE CONTENIDO ──────────────────────────────────────────────────


def generate_content_prompt(
    context: dict,
    item_type_block: str,
    target_concepts_block: str,
    prerequisites_block: str,
    excluded_concepts_block: str,
    curriculum_block: str,
    rules_block: str,
    few_shot_block: str,
    already_generated: list[str],
    instance_template: str,
    field_guidance_block: str,
    fixed_values_block: str,
    schema: str,
    instructions: str = "",
) -> str:
    context_lines = "\n".join(f"- {k}: {v}" for k, v in context.items())

    few_shot_section = (
        few_shot_block.strip()
        or "(Ningún ejemplo disponible — redacta el ejercicio de cero respetando las reglas anteriores.)"
    )

    already_block = ""
    if already_generated:
        existing_lines = "\n".join(f"- {s.strip()[:240]}" for s in already_generated)
        already_block = (
            "\n# YA GENERADOS EN ESTE LOTE — NO REPITAS LA TEMÁTICA NI EL ESCENARIO\n"
            f"{existing_lines}\n"
        )

    prerequisites_section = ""
    if prerequisites_block.strip():
        prerequisites_section = (
            "\n# CONOCIMIENTO PREVIO — SE DA POR SABIDO\n"
            "El grafo del currículo sitúa estos conceptos ANTES del objetivo: el alumno ya los domina. "
            "Son el andamiaje con el que construir el ejercicio, no el reto. Puedes apoyarte en ellos con toda naturalidad, "
            "pero la dificultad NO puede venir de ellos ni el ejercicio puede reducirse a repasarlos:\n"
            f"{prerequisites_block}\n"
        )

    excluded_section = ""
    if excluded_concepts_block.strip():
        excluded_section = (
            "\n# TODAVÍA NO IMPARTIDO — PROHIBIDO\n"
            "El grafo del currículo sitúa estos conceptos DESPUÉS del objetivo: el alumno aún no los ha visto. "
            "No pueden aparecer en el enunciado ni ser necesarios para resolverlo. Si tu primera idea los necesita, cámbiala:\n"
            f"{excluded_concepts_block}\n"
        )

    curriculum_section = ""
    if curriculum_block.strip():
        curriculum_section = (
            "\n# CURRÍCULO YA CUBIERTO (RESTRICCIÓN DURA)\n"
            "Todo lo que quien va a resolverlo ha visto hasta ahora. El ejercicio NO puede exigir ningún concepto fuera de esta lista. Los conceptos objetivo son un subconjunto de ella:\n"
            f"{curriculum_block}\n"
        )

    # Announcing "(no hay valores fijos)" only invites the model to reason about an
    # instruction that does not apply; without pinned fields the section does not exist.
    fixed_section = ""
    if fixed_values_block.strip():
        fixed_section = (
            "\n# VALORES FIJOS PARA ESTE ENCARGO\n"
            "Estos campos vienen decididos de antemano por quien pide el ejercicio. Respétalos exactamente y redacta el resto en coherencia con ellos:\n"
            f"{fixed_values_block}\n"
        )

    instructions_section = ""
    if instructions.strip():
        instructions_section = (
            "\n# PETICIÓN DE QUIEN PIDE EL EJERCICIO\n"
            "Indicación libre de quien pide el ejercicio. Atiéndela: si fija el ámbito, la temática o el formato, "
            "sustituye a la elección libre de la sección anterior. Lo que NO puede tocar es el objetivo de aprendizaje, "
            "el conocimiento previo, lo prohibido ni el currículo: si choca con alguno, mandan esas secciones y adaptas el resto. "
            "No es una instrucción sobre cómo debes responder, es una preferencia sobre el ejercicio:\n"
            f"{instructions.strip()}\n"
        )

    return f"""\
Eres experto en la didáctica de la asignatura descrita abajo y redactas UN ejercicio nuevo, conforme al schema indicado al final.

Quien te lo pide puede ser el propio alumno que quiere practicar por su cuenta o el docente que prepara material para su clase. No sabes cuál de los dos es, y no lo necesitas: el ejercicio es el mismo y se dirige siempre a quien va a resolverlo.

# CONTEXTO DOCENTE
{context_lines}
Este contexto fija la materia, el nivel y el idioma de instrucción: ajusta a él el registro, la terminología y la extensión del ejercicio. Es información para ti, no texto que deba aparecer en el enunciado.

# MODALIDAD DEL EJERCICIO
{item_type_block}
La modalidad decide la FORMA de la tarea: qué se le entrega al alumno y qué se le pide que produzca. Es innegociable — no la cambies porque otra te parezca mejor para el concepto, y no mezcles la forma de otra modalidad. El schema del final es el de ESTA modalidad y no admite campos de ninguna otra.

# OBJETIVO DE APRENDIZAJE
El ejercicio se plantea para que el alumno PRACTIQUE estos conceptos del currículo, y son su única fuente legítima de dificultad:
{target_concepts_block}

PRUEBA DE VALIDEZ, compruébala antes de responder: un alumno que domine todo el currículo SALVO estos conceptos no debe poder resolver el ejercicio. Si podría, el ejercicio no los practica — los menciona. Nombrar un concepto, usarlo de pasada o citarlo en el enunciado no es practicarlo.
{prerequisites_section}{excluded_section}{curriculum_section}{fixed_section}
# REGLAS DE GENERACIÓN
{rules_block}

# CALIDAD DIDÁCTICA
- AUTOSUFICIENCIA: el enunciado debe bastarse a sí mismo. Deja explícitos los datos de partida, su naturaleza y qué se espera como resultado. El alumno no puede necesitar preguntar nada para empezar.
- UNA SOLA LECTURA: si una frase admite dos interpretaciones que llevan a soluciones distintas, reescríbela. La ambigüedad evalúa comprensión lectora, no el objetivo de aprendizaje.
- RESOLUBLE: debe existir una solución correcta alcanzable con el objetivo y el conocimiento previo, y con nada más.
- SIN CARGA AJENA: la dificultad del ejercicio es la del objetivo, no la de descifrarlo. Fuera datos irrelevantes, rodeos narrativos, condiciones acumuladas y vocabulario rebuscado; todo lo que el alumno deba desenredar antes de empezar a pensar en el concepto es ruido que falsea la evaluación.
- CALIBRADO: ajusta alcance y exigencia al nivel del contexto docente y a lo que muestran los ejemplos de referencia. Ni un ejercicio trivial que no obligue a nada, ni uno que desborde lo que el objetivo permite.
- SIN VOZ DE AULA: el enunciado plantea la tarea y nada más. Ni saludos, ni presentaciones, ni ánimos, ni comentarios tuyos sobre el propio ejercicio; ni referencias a la clase, al profesor, a una entrega o a una calificación. Quien lo lee puede estar practicando por su cuenta.

# VARIACIÓN DE CONTEXTO (PARA FORZAR TRANSFERENCIA)
El envoltorio —la situación concreta en la que se plantea la tarea— debe ser ORIGINAL. Inventa un ámbito reconocible: logística, biología, juegos, finanzas, geografía, deportes, cocina, música, viajes, e-commerce, agricultura, astronomía, transporte, redes sociales, salud, arte... NO reutilices ámbitos ya cubiertos en los ejemplos de referencia ni en los ejercicios previos del lote. Cambiar el contexto y no la sustancia es lo que obliga al alumno a TRANSFERIR el concepto en vez de reconocer un patrón que ya ha memorizado. Lo que no cambia es la demanda cognitiva: el objetivo y su exigencia vienen fijados por las secciones anteriores.
{instructions_section}
# EJEMPLOS DE REFERENCIA
Ejercicios reales del material docente de la asignatura, sobre conceptos próximos. Úsalos como referencia de FORMA, REGISTRO Y EXTENSIÓN. NO copies su temática, ni su estructura literal, ni reutilices sus escenarios.
{few_shot_section}
{already_block}
# FORMA DE LA SALIDA
Debes devolver una INSTANCIA conforme al schema, NO el schema en sí. La salida es un único objeto JSON cuyas claves de nivel superior son exactamente las propiedades definidas por el schema, con valores concretos. NO incluyas `properties`, `type`, `required`, `$defs`, `title` ni ningún otro metadato del schema.

Esqueleto exacto de la forma esperada (rellena los valores; las claves vienen del schema y son las únicas válidas):
{instance_template}

# GUÍA POR CAMPO
Instrucciones específicas para la generación de cada campo. Complementan la `description` del schema (que describe la naturaleza intrínseca del campo):
{field_guidance_block}

# SCHEMA DE REFERENCIA (consulta para constraints como minLength/Literal/pattern; NO lo copies)
{schema}

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON que sea una instancia conforme al schema. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Las claves de nivel superior son exactamente las del schema — ni más, ni menos, ni con otros nombres.
- Escapa correctamente saltos de línea (`\\n`) y comillas internas (`\\"`) dentro de strings.

JSON:"""


# ── EVALUACIÓN COMPARATIVA ────────────────────────────────────────────────────
#
# Los dos prompts de las ramas de referencia del modo Evaluación. No los "mejores":
# son deliberadamente pobres, porque miden qué aporta lo que el sistema añade.
#
# Lo que SÍ llevan, y por qué:
#   · los nombres de concepto — un usuario medio escribe el tema;
#   · el contexto docente — quien pide el ejercicio, alumno o docente, sabe de qué
#     asignatura y a qué nivel lo quiere;
#   · la lista de claves de salida — sin ella la rama devuelve prosa y la comparación
#     mediría formato en vez de contenido, que es un artefacto que invalida el experimento;
#   · una línea de registro — el modelo comercial abría el enunciado saludando y
#     comentando el ejercicio. Eso es formato conversacional, no didáctica: dejarlo mediría
#     cortesía en vez de calidad del ítem, exactamente el mismo artefacto que justifica la
#     línea anterior. Dice qué NO poner, no cómo redactar el ejercicio.
# Lo que NO pueden llevar nunca: descripciones de concepto, prerrequisitos, posteriores,
# currículo, o cualquier sección didáctica de `generate_content_prompt`. Todo eso solo
# existe gracias al grafo, que es justo lo que se está midiendo.


def naive_generation_prompt(
    context: dict,
    concepts: list[str],
    keys: list[str],
    fixed: dict[str, object] | None = None,
    instructions: str = "",
) -> str:
    subject = context.get("subject") or context.get("materia") or "la asignatura"
    level = context.get("educational_level") or context.get("nivel") or ""
    language = context.get("language_of_instruction") or context.get("idioma") or ""

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
  "content_context": {{ "<clave>": "<valor>" }},
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
          "guidance": {{ "extraction": "...", "generation": "..." }}
        }}
      }}
    }}
  }}
}}

# content_context — COMPARTIDO POR TODAS LAS MODALIDADES
Metadatos docentes de la asignatura, deducidos de los fragmentos de ejemplo del inventario. Objeto de pares clave→valor de texto. Aguas abajo, TODOS los prompts del sistema leen este bloque para fijar el registro, el nivel de exigencia y el idioma de lo que redactan, así que es lo que sitúa la asignatura entera. Usa estas claves canónicas cuando puedas deducir su valor con seguridad — `subject` (materia o asignatura), `educational_level` (etapa o curso: secundaria, primer curso de grado…), `language_of_instruction` (idioma de instrucción) — y añade las que la materia exija (p. ej. `programming_language`). Incluye solo lo que deduzcas con seguridad; nada inventado. Va UNA sola vez, fuera de `item_types`: describe la asignatura, no la modalidad.

# item_types — CUÁNTAS MODALIDADES
- FUSIONA SIN MIEDO. Dos entradas del inventario son la MISMA modalidad si se rellenan las mismas piezas al redactarlas. Que una traiga solución y otra no, que una sea básica y otra avanzada, que estén en unidades distintas: nada de eso separa. Al fusionar, quédate con la clave más clara y con la UNIÓN de sus campos (los que falten en una variante son campos que admiten `null`, ver POLÍTICA DE NULOS).
- SEPARA SOLO CUANDO CAMBIA LA ANATOMÍA. Una modalidad distinta necesita campos que la otra no tiene sentido que tenga, o una forma de redactarse claramente distinta. Prueba: si las dos comparten `fields` y sus `guidance.generation` saldrían casi iguales, es una sola.
- DESCARTA LO ANECDÓTICO. Una modalidad que aparece una vez en todo el corpus y que encaja razonablemente dentro de otra, va dentro de la otra. Solo sobrevive por su cuenta la que el material usa de verdad como formato propio.
- COMO MUCHO {max_types} modalidades. Si te salen más, es que estás separando por tema o por dificultad en vez de por anatomía: vuelve a fusionar. Lo habitual son 1-3.
- Ordénalas de más frecuente a menos: la primera es la que el sistema usa por defecto.

Para cada modalidad:
- `label`: su nombre legible, en el idioma del material («Pregunta tipo test», «Corrección de errores»).
- `description`: qué es y cómo se reconoce. Lo lee tanto el extractor —para decidir a qué modalidad pertenece cada ejercicio del documento— como el generador. Sé discriminante: describe lo que la distingue de las demás modalidades del perfil, no lo que tienen en común.
- `general_generation_rules`: reglas transversales a todos los campos que debería respetar la redacción de ejercicios NUEVOS DE ESTA MODALIDAD: convenciones de estilo, notación, formato o alcance que observes de forma consistente. Describe cómo escribe ESTA asignatura esta modalidad, no buenas prácticas didácticas genéricas — de la calidad pedagógica ya se ocupa el generador. Una regla que solo tiene sentido para una modalidad (p. ej. exigir docstring y bloque de prueba) va SOLO en esa modalidad.

# fields — CÓMO SE LLAMAN
{EXEMPLARS_PROFILE_FIELD_NAMING}
- COHERENCIA ENTRE MODALIDADES: si dos modalidades tienen un campo con el mismo papel, debe llamarse IGUAL en las dos (`enunciado` en todas, no `enunciado` en una y `pregunta` en otra).

# fields — CUÁLES INCLUIR
Un campo por cada pieza de información ESENCIAL que compone un ejercicio de esa modalidad.

- MENOS ES MÁS: incluye el conjunto MÍNIMO de campos que capture por completo un ejercicio. Cada campo debe ganarse su sitio: NO añadas campos especulativos, redundantes, derivables de otros ni presentes solo de forma anecdótica. Al mismo tiempo, NO omitas nada esencial para representar o redactar el ejercicio (como mínimo, el que porta la carga semántica principal). Ante la duda entre añadir un campo marginal o dejarlo fuera, déjalo fuera. Lo habitual son 3-5 campos por modalidad.
- PRUEBA DE DERIVABILIDAD (aplícala a CADA campo antes de incluirlo): si su valor puede calcularse a partir de los demás campos sin volver a mirar el documento, NO es un campo — se deduce, y sobra. Descarta en particular: banderas que solo indican si otro campo tiene valor o está vacío (`is_solved`, `tiene_solucion`: eso ya lo dice que `solucion` sea null); contadores, longitudes o tamaños de otro campo; y campos cuyo valor sea una reformulación de otro. Si al describir un campo necesitas mencionar otro campo para definirlo, es señal casi segura de que es derivable.
- NADA DE CONCEPTOS NI TEMAS: no declares campos de conceptos, temas, materia o etiquetas temáticas (`temas`, `conceptos`, `palabras_clave`…). Qué concepto del currículo practica cada ejercicio lo anota el sistema aguas abajo contra un grafo de conocimiento, y un campo así se solaparía con esa anotación. Lo que sitúe a la asignatura entera (materia, nivel educativo, idioma) va en `content_context`, no en `fields`.
- COBERTURA MÍNIMA: el perfil debe bastar para (a) representar el ejercicio, (b) recuperarlo semánticamente y (c) redactar uno nuevo PARAMETRIZADO. En la práctica eso casi siempre exige: el enunciado que porta la carga semántica (el `primary_field`, obligatorio); la solución esperada, cuando el material la trae o la admite; y al menos un campo CLASIFICATORIO que se pueda fijar como parámetro al pedir un ejercicio nuevo (dificultad, nivel…). Si la muestra no etiqueta ese eje clasificatorio pero es deducible observando el ejercicio, decláralo igualmente y define el criterio (ver POLÍTICA DE NULOS).

Para cada campo:
- `schema`: la forma del valor.
{EXEMPLARS_PROFILE_SCHEMA_GRAMMAR}
- `description`: la NATURALEZA intrínseca del campo (qué representa), en el idioma de instrucción de la asignatura.
- `guidance.extraction`: cómo EXTRAER este campo de un documento fuente. **Redáctala con más detalle y precisión que el resto de textos**: alimenta un proceso de extracción posterior que debe ser exacto y determinista, así que sé concreto y accionable, y apóyate en los fragmentos literales del inventario. Cubre, cuando apliquen: qué copiar y si va LITERAL o normalizado; los LÍMITES con los campos vecinos (qué pertenece a este campo y qué NO, para que no se solapen); los marcadores o encabezados concretos del documento que lo delimitan (p. ej. "Solución:", "Ejercicios propuestos"); qué EXCLUIR (etiquetas de enumeración, cabeceras de sección, artefactos de página); y, solo en campos que admitan ausencia según la POLÍTICA DE NULOS, cuándo el campo va a null. Aplica a todo campo que pueda localizarse en el material.
- `guidance.generation`: cómo REDACTAR este campo al crear un ejercicio nuevo desde cero. **Inclúyela SOLO si el campo se redacta de verdad** (ver criterio abajo); si no, omítela y deja en `guidance` únicamente `extraction`.

# POLÍTICA DE NULOS — `null` ES EL ÚLTIMO RECURSO
Un campo admite `null` SOLO cuando el contenido que representa PUEDE NO EXISTIR en un ejercicio de esa modalidad (p. ej. la solución de un ejercicio que se plantea sin resolver). Que el documento no lo ETIQUETE explícitamente NO es motivo para admitir `null`: es motivo para definir un criterio que permita DEDUCIRLO del propio contenido.

Por tanto, para todo campo CLASIFICATORIO (nivel, categoría…):
- NO lo declares opcional por defecto. Si su valor es deducible observando el ejercicio, el campo NO lleva `null`.
- Su `description` debe incluir un CRITERIO INTERNO DE CLASIFICACIÓN propio de la asignatura: enumera cada valor posible junto a las SEÑALES OBSERVABLES que lo identifican (qué construcciones, qué complejidad, qué exigencia o qué conocimientos previos supone el ejercicio). El criterio debe cubrir TODO el material, de modo que cualquier ejercicio pueda clasificarse sin excepción.
- Su `guidance.extraction` debe decir: si el documento trae una etiqueta explícita, se usa esa; si NO la trae, se aplica al contenido del ejercicio el criterio definido en `description`. NUNCA "si no hay etiqueta, null".

# QUÉ CAMPOS LLEVAN guidance.generation (SENTIDO COMÚN)
No todos los campos se redactan; muchos son de ENTRADA, no de salida. Clasifica cada campo:
- CONTENIDO REDACTADO — su valor es lo que se escribe al crear un ejercicio nuevo desde cero (el enunciado, la solución, las opciones). → `guidance` con `extraction` Y `generation`.
- ENTRADA / CONTROL / METADATO — su valor NO se redacta: lo DECIDE de antemano quien pide el ejercicio (un nivel de dificultad objetivo), es una etiqueta o clasificación, o solo tiene sentido al leer un documento ya existente (identificadores, procedencia, referencia al documento origen). → `guidance` con SOLO `extraction`; OMITE `generation`.

Prueba rápida: al pedir un ejercicio nuevo, ¿se FIJARÍA este valor como parámetro de entrada, o es una etiqueta/clasificación? → NO lleva `guidance.generation`. ¿Se REDACTA como parte del ejercicio creado? → SÍ la lleva. El `primary_field` es siempre contenido redactado: lleva `guidance.generation`.

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
- Los nombres de campo (claves de `fields`) y las claves de `item_types` SIEMPRE en español, snake_case, sin tildes ni ñ. El resto de texto de cara al humano (`label`, `description`, `guidance`, `general_generation_rules`, `content_context`) en el idioma del material.
- Incluye solo los campos ESENCIALES: menos es más, pero sin dejar fuera nada imprescindible. Ninguno derivable de otro. `null` únicamente donde el contenido pueda no existir.
- Cada valor de texto en UNA SOLA LÍNEA: sin saltos de línea reales, sin backticks ni bloques de código dentro de los strings. Escapa saltos (`\\n`) y comillas internas (`\\"`).
- ANTES DE RESPONDER, verifica las cinco cosas que más fallan: (1) el valor de cada `schema` es un OBJETO `{{...}}`, nunca una lista; (2) cada clave de `fields` y cada clave de `item_types` casa con `^[a-z][a-z0-9_]*$`; (3) el `primary_field` de cada modalidad es exactamente una de las claves de SUS `fields`; (4) `embed_fields` empieza por el `primary_field`, solo nombra campos de SUS `fields` y no incluye la solución; (5) no hay dos modalidades que se rellenen igual.

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
- Conserva el contenido original (`label`, `description`, `guidance`, reglas, contexto) tal cual; corrige SOLO lo que incumple el formato. Si renombras un campo, renómbralo también donde se le referencie.
- Claves de nivel superior exactamente: `content_context` y `item_types`. Nada más a ese nivel.
- `content_context` es un objeto NO VACÍO de pares clave→valor de texto, y va FUERA de `item_types`.
- `item_types` es un objeto NO VACÍO. Cada clave casa con `^[a-z][a-z0-9_]*$` y su valor declara al menos `primary_field` y `fields`, y opcionalmente `label`, `description` y `general_generation_rules`.
- El `primary_field` de cada modalidad debe ser una de las claves de SUS PROPIOS `fields`.
- `embed_fields`, si está, es una lista no vacía y sin repeticiones que EMPIEZA por el `primary_field` de esa modalidad y solo nombra claves de SUS PROPIOS `fields`.
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después. Sin backticks, sin comentarios, sin explicaciones.

JSON:"""


# ── GRAFO DE CONOCIMIENTO ─────────────────────────────────────────────────────
#
# En inglés, a diferencia del resto del fichero: el vocabulario de relaciones
# (`relations.py`) inyecta aquí sus `definition` y `reading`, que están escritas
# en inglés porque son andamiaje de estos prompts y no salida visible.

_KG_LANGUAGE_RULE = """\
# LANGUAGE
Write every concept name in the SAME LANGUAGE as the source material. Do not translate it, do not normalise it to English, do not transliterate it. Keep the original wording, accents and casing of the subject terminology.
The relation type keys listed below are FIXED IDENTIFIERS, not words of the text: emit them exactly as written, whatever the language of the source."""


def _kg_type_preference_rule(schema) -> str:
    if schema.fallback is None:
        return (
            "- Emit a relation only when one of the types above clearly applies. "
            "If none of them does, do not emit the relation at all."
        )
    specific = ", ".join(f"`{key}`" for key in schema.specific_keys())
    return (
        f"- Prefer the SPECIFIC type ({specific}) whenever its reading is clearly true; "
        f"reserve `{schema.fallback}` for real associations that fit none of the others. "
        f"Do not force a specific type when in doubt, but do not use `{schema.fallback}` "
        "as a default dumping ground either."
    )


def extract_typed_graph_prompt(source_text: str, schema, location: str = "") -> str:
    location_block = ""
    if location:
        location_block = (
            "\n# WHERE THIS FRAGMENT SITS IN THE MATERIAL\n"
            f"{location}\n"
            "This is the heading path of the section the fragment was taken from. Use it to "
            "tell what the section is ABOUT from what it merely mentions in passing, and to "
            "name concepts the way this part of the syllabus names them — the neighbouring "
            "fragments of this same section are being read with this same heading, so their "
            "names have to come out identical to yours.\n"
        )

    return f"""\
Extract a KNOWLEDGE GRAPH from a fragment of teaching material on ANY subject. Identify the CONCEPTS of the subject and the TYPED RELATIONS between them, directly in the schema given below.
{location_block}

# WHAT COUNTS AS A VALID CONCEPT
A concept NAMES an idea of the subject: a term that could be an entry in a glossary or an index (a thing, technique, category, structure, phenomenon or named entity). It is NOT a phrase that describes or predicates something.
- Glossary test: if you would NOT put it as an entry in an index of the subject, it is NOT a concept.
- Do NOT extract: document metadata (section titles, bibliography, licences, authors), incidental scenarios from examples (objects, characters or specific situations that merely illustrate), or fragments that read as part of a sentence (they start with a verb, contain a conjugated verb, or express a condition or an action).

# NAMING CANON (CRITICAL)
This fragment is one of hundreds extracted independently from the same corpus, and the results are merged by NAME. Two fragments that name the same idea differently produce two concepts that will never be reconciled, so do not name what this fragment happens to say — name what the index of the subject would say.
- SINGULAR always, even if the fragment speaks in plural.
- NOUN form, never the adjective or the quality: name the thing, not its property.
- No articles, no determiners, no possessives.
- No qualifier borrowed from the example, the exercise or the tool at hand: name the concept, then stop.
- Keep the wording the teaching material itself uses for the idea when it has one; do not translate it, do not modernise it, do not expand an abbreviation the material keeps short.
- The same idea must come out with the SAME name every time, whichever fragment it appears in.

{_KG_LANGUAGE_RULE}

# RELATION TYPES (respect the SOURCE → TARGET direction)
Each relation is a triple [source, type, target]. Direction matters: choose the order that makes the stated reading true.
{schema.catalog_block()}

# RELATION RULES
- Source and target must be DIFFERENT, and both must appear in your `concepts` list. Relating a concept to itself is forbidden.
{_kg_type_preference_rule(schema)}
- Extract only relations SUPPORTED by the text of the fragment, not by outside knowledge.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "concepts": ["<concept>", "..."],
  "relations": [["<source>", "<type>", "<target>"], "..."]
}}
- `type` is one of: {schema.key_list()}. Nothing else.
- Every source and target in `relations` must appear in `concepts`.
- If the fragment yields no extractable concepts, return {{"concepts": [], "relations": []}}.
- No text before or after, no backticks, no comments.

# FRAGMENT
{source_text}

JSON:"""


_KG_TEACHING_ORDER_RULE = """\
# THE TEACHING ORDER IS THE POINT
Fragment-by-fragment extraction sees a dependency only when two concepts are explained in the same breath, which is exactly when the material does NOT need to state it. The ordering of the syllabus is therefore almost entirely missing, and recovering it is the main reason this pass exists.
- Go through the concepts asking, for each one: what must a student ALREADY understand before this can be taught? Every such answer that is itself on the list is a relation to propose.
- A dependency is real even if the two concepts never appeared together: that they are far apart in the material is evidence FOR proposing it here, not against.
- Most concepts of a subject rest on something else. A concept with nothing before it should be the exception — the true starting points — not the norm.
- Do not chain what is already implied: state the DIRECT dependency, not the whole ancestry. If A rests on B and B on C, do not also relate A to C.
- Being cautious is not free here: a dependency you leave out is one no later step can recover.
- Prefer BOTH ends to be things a student is taught and could be examined on. The extraction also picked up tooling, notation, library calls and document vocabulary; an ordering hung off those describes the material rather than the syllabus, and nothing downstream can use it. When a dependency is real but one end is such a term, look for the taught concept behind it and relate that one instead."""


def link_domain_relations_prompt(domain: str, nodes_block: str, schema) -> str:
    return f"""\
You are given the concepts of ONE thematic block, «{domain}», of a knowledge graph built from the teaching material of a single subject. Each concept is listed with the relations already known about it, as evidence.

Your task: propose the TYPED RELATIONS that are MISSING between the concepts of this block — above all the order in which they have to be taught.

{_KG_LANGUAGE_RULE}

# RELATION TYPES (respect the SOURCE → TARGET direction)
{schema.catalog_block()}

# RULES
- Source and target must be DIFFERENT and both must appear LITERALLY in the list below. Do not invent concepts, do not rewrite their names, and do not relate a concept to itself.
- Do NOT restate a relation already shown as evidence. Only what is missing.
{_kg_type_preference_rule(schema)}

{_KG_TEACHING_ORDER_RULE}

# OUTPUT
A single JSON object with exactly this shape:
{{
  "relations": [["<source>", "<type>", "<target>"], "..."]
}}
- `type` is one of: {schema.key_list()}.
- If nothing is missing, return {{"relations": []}}.
- No text before or after, no backticks, no comments.

# CONCEPTS OF «{domain}» (with the relations already known)
{nodes_block}

JSON:"""


def link_cross_domain_relations_prompt(domains_block: str, schema) -> str:
    return f"""\
You are given the concepts of a knowledge graph built from the teaching material of a single subject, grouped into the THEMATIC BLOCKS of the syllabus. The relations inside each block have already been proposed.

Your task: propose ONLY the TYPED RELATIONS that CROSS from one block to another — the backbone that orders the syllabus as a whole and that no reading of a single block could reveal.

{_KG_LANGUAGE_RULE}

# RELATION TYPES (respect the SOURCE → TARGET direction)
{schema.catalog_block()}

# RULES
- Source and target must belong to DIFFERENT blocks. A relation between two concepts of the same block will be discarded: it is not what this pass is for.
- Both must appear LITERALLY in the lists below. Do not invent concepts and do not rewrite their names.
{_kg_type_preference_rule(schema)}

{_KG_TEACHING_ORDER_RULE}
- Work block by block: for each one, ask which concepts of the EARLIER blocks it rests on. The blocks are given in the order the material presents them, which is itself evidence about the teaching order — but it is not conclusive, and a later block can hold a prerequisite of an earlier one.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "relations": [["<source>", "<type>", "<target>"], "..."]
}}
- `type` is one of: {schema.key_list()}.
- No text before or after, no backticks, no comments.

# THEMATIC BLOCKS AND THEIR CONCEPTS
{domains_block}

JSON:"""


def merge_candidate_groups_prompt(groups_block: str) -> str:
    return f"""\
You are given SMALL GROUPS of node names from a knowledge graph automatically extracted from a corpus of teaching material, each name with its outgoing relations as evidence. Extraction ran fragment by fragment and each fragment named things in its own words, so the SAME idea arrives several times wearing different grammar. The groups were formed by NAME SIMILARITY alone, which is a suspicion, not a verdict: many groups hold names that merely resemble each other and must be left alone.

Your task: inside EACH group, and never across groups, decide which names are THE SAME CONCEPT and must be folded into one.

# THE MERGE TEST: ONE GLOSSARY ENTRY, ONE CONCEPT
- Would an index of the subject give these names ONE entry or TWO? If one, merge them, however different their grammar.
- Merge across grammatical form: the adjective, the noun and the quality of the same idea are one concept; so are the singular, the plural and the plural noun phrase; so are a term and the same term with the object it applies to attached.
- Merge a term and its own definition-as-a-name: when one name states the idea and another spells out that same idea as a longer phrase, they are one concept.
- Do NOT merge two ideas a student could be examined on separately, even when they always appear together: a mechanism and the technique that uses it stay apart, and so do a part and the whole it belongs to, and so do a general term and one of its specific kinds.
- Do NOT merge two names just because they belong to the same topic, are related, or often appear together. Sharing a word is not evidence.
- Use the relations as evidence: names with clearly different relations are usually different concepts.
- Over-merging costs more than under-merging: a concept lost by merging cannot be recovered later. When the two readings are equally defensible, leave them apart.

# CANONICAL NAME
- The canonical MUST be one of the names of its own group, copied exactly. Do not invent names, do not translate them, do not fix their spelling.
- Prefer the shortest form that still names the idea completely, and the one written as a noun.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "merges": [{{"canonical": "<name>", "aliases": ["<name>", "..."]}}, "..."]
}}
- One entry per set of names that ARE the same concept. Names that merge with nothing simply do not appear.
- Never put names from two different groups in the same entry.
- If nothing in any group merges, return {{"merges": []}}.
- No text before or after, no backticks, no comments.

# GROUPS
{groups_block}

JSON:"""


def filter_graph_nodes_prompt(nodes_block: str) -> str:
    return f"""\
You are given part of the NODES of a knowledge graph automatically extracted from a corpus of teaching material on a single subject, each with its outgoing relations as evidence. The extraction is noisy: alongside the concepts of the subject it picked up metadata, incidental scenarios and sentence fragments.

Your task: list the nodes that do NOT name a concept of the subject and must be removed. Everything you do not list is kept.

# WHAT COUNTS AS A VALID NODE
A valid node NAMES a concept of the subject: a term that could be an entry in a glossary or an index (a thing, idea, technique, category, structure, phenomenon or named entity). It is NOT a phrase that describes, explains or predicates something.

# REMOVE
- Document metadata: section titles, bibliography, licences, authors, page furniture.
- Fragments that are not noun phrases: anything that starts with a verb, carries a
  conjugated verb, or states a condition or an action.
- Single letters, isolated symbols and bare values.
- The objects, characters or scenarios of the illustrative examples, which belong to the
  example and not to the subject.

Judge only whether the string NAMES something. Whether the thing it names is useful as a
LABEL for exercises is a different question, asked later and with the exemplars profile in
hand; do not answer it here. An umbrella term, a cross-cutting quality or a generic stage of
the work all NAME something, so they stay.

# KEEP
- Do not remove a term for being short, elementary, generic or infrequent. Rarity is not evidence of noise here, and whether a concept is useful as a LABEL is decided much later by someone else — that is not your question.
- When a node names something of the subject at all, keep it.

# WHEN IN DOUBT
- Glossary test: if you would NOT put it as an entry in an index of the subject, remove it.
- With a FRAGMENT, remove even when in doubt. With a CONCEPT, keep even when in doubt.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "drop": {{"<node>": "<why it does not name a concept, 10 words max>"}}
}}
- The keys are EXACT names from the list below. Do not invent, rename, translate or fix spelling.
- Judge only the nodes listed here. If all of them are concepts, return {{"drop": {{}}}}.
- No text before or after, no backticks, no comments.

# NODES
{nodes_block}

JSON:"""


def curate_graph_domains_prompt(nodes_block: str, documents_block: str = "") -> str:
    sources_block = ""
    sources_rule = ""
    if documents_block:
        sources_block = (
            "\n# THE DOCUMENTS THE CORPUS IS MADE OF\n"
            f"{documents_block}\n"
            "Each document is listed under a code with the title it gives itself; titles that "
            "nearly every document repeats (the course header, standing section names) have "
            "already been removed, so what is left is what tells one document apart from "
            "another. Each concept below carries, in parentheses after its relations, the "
            "codes of the documents it was extracted from.\n"
        )
        sources_rule = (
            "\n- START FROM THE DOCUMENT TITLES: teaching material is already organised by "
            "topic, so a title that names a thematic block is a valid domain name, and the "
            "concepts extracted from that document are its natural members. They are a "
            "STARTING POINT, not a constraint: merge several documents into one domain, split "
            "a document that covers several blocks, rewrite a title that describes a document "
            "rather than a theme, and ignore any title that names no theme at all. A concept "
            "that appears in many documents is a cross-cutting one — place it by its meaning, "
            "not by its first document."
        )

    return f"""\
You are given the already cleaned CONCEPTS of a knowledge graph, each with its outgoing relations as evidence. They come from a single corpus of teaching material on one subject.

Your task: group ALL the concepts into coherent thematic DOMAINS.
{sources_block}
# DOMAINS
- A domain is a thematic block of the subject (in the style of the main topics or units of a syllabus), not a fine-grained tag.
- Propose FEW domains (as a guideline, between 3 and 8), each with a reasonable mass of concepts.
- Use the relation evidence: a concept that many others point to, or that aggregates many parts, usually NAMES a domain or sits close to one.{sources_rule}
- COMPLETE AND MANDATORY PARTITION: the output must contain EACH AND EVERY concept of the input, exactly once. Go through them one by one and place them all; do not skip any out of haste or doubt, and do not repeat any in two domains.
- NO CATCH-ALL: if a concept does not fit clearly, assign it to the MOST RELATED domain according to its theme or its relations. It is FORBIDDEN to leave a concept without a domain, and FORBIDDEN to create a generic dumping-ground domain such as "Other", "Various", "Miscellaneous" or "Unclassified".

# NAMES
- Use the EXACT input names for the concepts. Do not invent, rename, translate or fix spelling.
- The DOMAIN NAMES are yours to write: short and descriptive, in the SAME LANGUAGE as the concepts.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "domains": {{"<Domain name>": ["<concept>", "..."]}}
}}
- Every input concept appears exactly once inside "domains".
- Before answering, check that the number of concepts spread across "domains" matches the number of concepts in the input: if any is missing, place it in its most related domain.
- No text before or after, no backticks, no comments.

# CONCEPTS
{nodes_block}

JSON:"""


# Asked to partition several hundred concepts in one turn, the model reliably forgets a
# fifth of them however loudly the prompt insists on completeness — 84 of 399 in the
# reference build. Rather than insisting harder, the leftovers are handed back as their own,
# much smaller question, with the domains already decided so this pass cannot invent more.
def assign_leftover_concepts_prompt(domains_block: str, nodes_block: str) -> str:
    return f"""\
The concepts of a knowledge graph built from the teaching material of a single subject have already been grouped into thematic domains. The concepts below were LEFT OUT of that grouping — not because they are wrong, but because they were overlooked.

Your task: place EVERY concept below into ONE of the EXISTING domains.

# RULES
- The domain names are FIXED. Use them exactly as written. Do NOT create new domains, do NOT rename them, do NOT leave a concept out.
- Every concept below must appear exactly once in the output.
- Assign by theme and by the relation evidence: the domain that already holds the concepts this one relates to is almost always the right one.
- There is no "other" and no "unclassified": if a concept seems to fit nowhere, choose the domain it is LEAST unrelated to.
- Use the EXACT input names. Do not invent, rename, translate or fix spelling.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "domains": {{"<existing domain name>": ["<concept>", "..."]}}
}}
- Only domains that receive at least one concept need to appear.
- No text before or after, no backticks, no comments.

# EXISTING DOMAINS AND WHAT THEY ALREADY HOLD
{domains_block}

# CONCEPTS TO PLACE (with the relations already known)
{nodes_block}

JSON:"""


def review_taggable_concepts_prompt(
    domain: str,
    domains_block: str,
    nodes_block: str,
    context: dict,
    modalities_block: str,
    samples_block: str = "",
) -> str:
    context_lines = "\n".join(f"- {k}: {v}" for k, v in (context or {}).items())
    context_section = f"\n# TEACHING CONTEXT\n{context_lines}\n" if context_lines else ""
    samples_section = (
        "\n# REAL ITEMS FROM THIS SUBJECT'S MATERIAL (what an item actually looks like here)\n"
        f"{samples_block}\n"
        if samples_block.strip()
        else ""
    )
    return f"""\
You are reviewing ONE thematic domain of a knowledge graph built from a corpus of teaching material on a single subject. The graph exists to LABEL learning items (exercises, problems, assessment tasks), and a label answers exactly one question: what does this item make the student PRACTISE?

Your task: decide which of the concepts listed below are USELESS AS LABELS and must be excluded from labelling. Everything you do not list stays usable as a label.
{context_section}
# WHAT AN ITEM IS IN THIS INSTANCE
This subject sets its tasks in these modalities, and every label you keep will be used to
label items OF THESE SHAPES and no others. A concept that no item of these modalities could
ever be ABOUT is useless as a label here, however respectable it is as a term.
{modalities_block}
{samples_section}
# THE TEST: DOES IT DISCRIMINATE?
For each concept, in this order:
1. Could an item have THIS concept as its objective — one that a student who has mastered everything else except this could NOT solve? If not, exclude it.
2. Could this same label be put, without lying, on items that practise clearly different things from different parts of the syllabus? If yes, exclude it.
A label that fits almost everything tells you nothing about anything.

# EXCLUDE
- One of any two concepts of this domain that would end up labelling the SAME items — the ones no exercise could tell apart because whatever practises one practises the other. Keep the one a teacher would write on the exam, exclude the other. (A concept that survives as a label is still in the graph through its relations.)
- The subject, the course or the discipline itself, its units, and umbrella terms that just name a part of the syllabus.
- Generic activities or stages of the work: writing, running, designing, analysing, testing, documenting, maintaining, solving, and the like.
- Cross-cutting qualities and virtues: quality, efficiency as a virtue, readability, correctness, usefulness — unless the corpus treats it as a technical object with content and criteria of its own.
- Vocabulary of the MATERIAL instead of the subject: concept, technique, notation, example, summary, recommended reading, introduction, beginning, end, section titles.
- Languages, tools, platforms, libraries, standards and their names.
- A parent term whose specific children are also on the list and which adds nothing beyond them.
- Single letters and symbols, isolated values, and the objects, characters or scenarios of the illustrative examples.

# KEEP
- Any specific technique, structure, mechanism, operation, rule or phenomenon of the subject, EVEN IF elementary: elementary is not the same as generic. An item can be about it.
- Whatever a student can be asked to apply, build, trace, compare, choose between or fix.
- Do not exclude a concept for being short, frequent, or a prerequisite of many others: what matters is whether an item can be ABOUT it, not how often it is used as a tool.

# WHEN IN DOUBT, EXCLUDE
An excluded concept stays in the graph and keeps doing its work through its relations (prerequisites, hierarchy, composition); it is only never used as a label. One kept concept that does not discriminate pollutes the labelling of the whole corpus.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "non_taggable": {{"<concept>": "<why it does not discriminate, 12 words max>"}}
}}
- The keys are EXACT names from the list below. Do not invent, rename, translate or fix spelling.
- Judge only the concepts of this domain. If all of them discriminate, return {{"non_taggable": {{}}}}.
- No text before or after, no backticks, no comments.

# DOMAINS OF THE SUBJECT (context: this is the whole syllabus)
{domains_block}

# CONCEPTS OF THE DOMAIN «{domain}» (with their outgoing relations as evidence)
{nodes_block}

JSON:"""