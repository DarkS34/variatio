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

{_KG_LANGUAGE_RULE}

# TIPOS DE RELACIÓN (respeta la dirección ORIGEN → DESTINO)
Cada relación es una terna [origen, tipo, destino]. La dirección importa: elige el orden que hace cierta la lectura enunciada.
{schema.catalog_block()}

# REGLAS DE RELACIÓN
- El origen y el destino deben ser DISTINTOS, y ambos deben aparecer en tu lista `concepts`. Está prohibido relacionar un concepto consigo mismo.
{_kg_type_preference_rule(schema)}
- Extrae solo las relaciones SOSTENIDAS por el texto del fragmento, no por conocimiento externo.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "concepts": ["<concepto>", "..."],
  "relations": [["<origen>", "<tipo>", "<destino>"], "..."]
}}
- El `<tipo>` es uno de: {schema.key_list()}. Nada más.
- Todo origen y todo destino de `relations` debe aparecer en `concepts`.
- Si el fragmento no da ningún concepto extraíble, devuelve {{"concepts": [], "relations": []}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

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

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "relations": [["<origen>", "<tipo>", "<destino>"], "..."]
}}
- El `<tipo>` es uno de: {schema.key_list()}.
- Si no falta nada, devuelve {{"relations": []}}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# CONCEPTOS DE «{domain}» (con las relaciones ya conocidas)
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
- Trabaja bloque a bloque: para cada uno, pregúntate en qué conceptos de los bloques ANTERIORES se apoya. Los bloques vienen en el orden en que el material los presenta, que es en sí mismo evidencia sobre el orden de enseñanza — pero no es concluyente, y un bloque posterior puede contener un prerrequisito de uno anterior.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "relations": [["<origen>", "<tipo>", "<destino>"], "..."]
}}
- El `<tipo>` es uno de: {schema.key_list()}.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# BLOQUES TEMÁTICOS Y SUS CONCEPTOS
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
- Asigna por tema y por la evidencia de las relaciones: el dominio que ya contiene los conceptos con los que este se relaciona es casi siempre el correcto.
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
    context: dict,
    modalities_block: str,
    samples_block: str = "",
) -> str:
    context_lines = "\n".join(f"- {k}: {v}" for k, v in (context or {}).items())
    context_section = f"\n# CONTEXTO DOCENTE\n{context_lines}\n" if context_lines else ""
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
