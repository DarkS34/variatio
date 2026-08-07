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


def format_content_prompt(
    content: str,
    schema: str,
    context: dict | None = None,
    field_guidance_block: str = "",
) -> str:
    context_block = ""
    if context:
        context_lines = "\n".join(f"- {k}: {v}" for k, v in context.items())
        context_block = f"\n# CONTEXTO DOCENTE DEL DOCUMENTO\n{context_lines}\n"

    field_guidance_section = ""
    if field_guidance_block.strip():
        field_guidance_section = (
            "\n# GUÍA DE EXTRACCIÓN POR CAMPO\n"
            "Instrucciones específicas sobre QUÉ extraer y CÓMO formatearlo en cada campo. Síguelas literalmente:\n"
            f"{field_guidance_block}\n"
        )

    return f"""\
Extrae los ITEMS DE APRENDIZAJE de un fragmento markdown pre-segmentado de material docente.

Un item de aprendizaje es toda unidad que el material PLANTEA AL ALUMNO COMO TAREA: un ejercicio, un problema, una actividad, una pregunta, un supuesto práctico. Que venga acompañado de su solución no lo descalifica — sigue siendo un item, con su solución incluida.

NO son items de aprendizaje y no deben extraerse: la exposición teórica del temario, las explicaciones y definiciones, los ejemplos que el texto usa para ILUSTRAR una explicación sin pedir nada al alumno, los índices, los objetivos de la unidad, las rúbricas, la bibliografía y los avisos administrativos. Si el fragmento no plantea ninguna tarea, devuelve `[]`.

El input contiene uno o varios items. Si hay varios, vienen separados por líneas `---`. Cada bloque entre separadores (o el input completo si es un único bloque) representa exactamente UN item. Dentro de un bloque, todo lo que encuentres — sub-preguntas, apartados (a/b/c, i/ii/iii), bloques de código embebidos, instrucciones de seguimiento, párrafos explicativos, tablas, ejemplos — pertenece a ese único item: los apartados son una progresión de la misma tarea, no tareas distintas.

Produce un JSON array con un objeto por item, conforme al schema de abajo.

# SCHEMA DE SALIDA
Cada objeto del array debe cumplir este JSON Schema. El campo `description` de cada propiedad describe la NATURALEZA del campo (qué representa). Para esta tarea de extracción, sigue además las instrucciones específicas que aparecen en «GUÍA DE EXTRACCIÓN POR CAMPO» más abajo.

{schema}
{field_guidance_section}
# REGLAS DE EXTRACCIÓN
- Copia los valores literalmente del texto fuente. No reescribas, no traduzcas, no resumas, no inventes contenido. Lo que se extrae es material docente real: alterarlo destruye justamente lo que lo hace útil como ejemplo.
- Si un campo admite null y el contenido no aparece en la fuente, ponlo a null. Nunca fabriques contenido para rellenar: un enunciado sin solución en el material es un item legítimo, uno con la solución inventada es material docente falso.
- Elimina marcadores de enumeración inicial (`1.`, `2)`, `Ejercicio 3:`, `Exercise 4.`, `Problema 5 -`, `Apartado 6:`, `Sección 7 –`, etc.) en los campos de texto. Los valores deben empezar con el primer carácter real del contenido, no con un número o etiqueta.
- Para strings multilínea (código, prosa con párrafos): escapa saltos como `\\n` y comillas internas como `\\"`.
- Respeta los constraints del schema (`minLength`, `maxLength`, `pattern`, etc.).

# REGLAS DE SALIDA
- Un único JSON array. Nada antes, nada después.
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
    siblings: list[str],
    context: dict,
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
        siblings_block = (
            f"\n# OTROS CONCEPTOS DEL MISMO BLOQUE TEMÁTICO\n{', '.join(siblings)}\n"
        )

    return f"""\
Estás generando la descripción del concepto del currículo «{concept}», del bloque temático «{domain}».
{context_block}{relations_block}{siblings_block}
# OBJETIVO
Esta descripción es la superficie con la que se decidirá, para cada ejercicio del material docente, QUÉ CONCEPTO DEL CURRÍCULO PRACTICA ese ejercicio. Se compara semánticamente contra el enunciado de los ejercicios, así que debe LEER COMO el enunciado de un ejercicio de este concepto, o como su primera frase — no como la definición de manual del concepto.

Describe QUÉ HACE EL ALUMNO cuando practica esto: la tarea observable que se le pide, no la teoría que hay detrás.

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

# REGLAS DE FORMA
- 1-4 frases, según haga falta para ser específico sin caer en lo genérico.
- Estilo "tarea que se le plantea al alumno para practicar este concepto", no definición formal.
- Apóyate en el contexto docente y en las relaciones para inferir el registro, el nivel y el vocabulario de superficie de la materia — términos, símbolos, sintaxis, fórmulas, identificadores o construcciones propias que aparecerían de verdad en ejercicios de esa asignatura y ese nivel. Lo que no aplique a esta materia, no lo uses.
- Idioma: el de instrucción que indique el contexto docente. Si no se desprende con claridad, usa el mismo idioma de los nombres de los conceptos.
- Texto plano sin ningún tipo de marcado: ni markdown, ni etiquetas estructuradas, ni cercos (backticks, fences, comillas envolventes).

Descripción:"""


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
Actúas como el docente que cataloga el banco de ejercicios de una asignatura. Para el ejercicio de abajo, decide QUÉ CONCEPTOS DEL CURRÍCULO hace practicar al alumno.
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
- `primary_concept`: el OBJETIVO DE APRENDIZAJE del ejercicio — aquello por lo que un docente lo pondría en un examen. Debe aparecer también en `concepts`.
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
            "\n# CURRÍCULO CUBIERTO POR EL ALUMNO (RESTRICCIÓN DURA)\n"
            "Todo lo que el alumno ha visto hasta ahora. El ejercicio NO puede exigir ningún concepto fuera de esta lista. Los conceptos objetivo son un subconjunto de ella:\n"
            f"{curriculum_block}\n"
        )

    # Announcing "(no hay valores fijos)" only invites the model to reason about an
    # instruction that does not apply; without pinned fields the section does not exist.
    fixed_section = ""
    if fixed_values_block.strip():
        fixed_section = (
            "\n# VALORES FIJOS PARA ESTE ENCARGO\n"
            "Estos campos vienen decididos de antemano por quien encarga el ejercicio. Respétalos exactamente y redacta el resto en coherencia con ellos:\n"
            f"{fixed_values_block}\n"
        )

    return f"""\
Eres docente de la asignatura descrita abajo y estás redactando UN ejercicio nuevo para tus alumnos, conforme al schema indicado al final.

# CONTEXTO DOCENTE
{context_lines}
Este contexto fija la materia, el nivel y el idioma de instrucción: ajusta a él el registro, la terminología y la extensión del ejercicio. Es información para ti, no texto que deba aparecer en el enunciado.

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

# VARIACIÓN DE CONTEXTO (PARA FORZAR TRANSFERENCIA)
El envoltorio —la situación concreta en la que se plantea la tarea— debe ser ORIGINAL. Inventa un ámbito reconocible: logística, biología, juegos, finanzas, geografía, deportes, cocina, música, viajes, e-commerce, agricultura, astronomía, transporte, redes sociales, salud, arte... NO reutilices ámbitos ya cubiertos en los ejemplos de referencia ni en los ejercicios previos del lote. Cambiar el contexto y no la sustancia es lo que obliga al alumno a TRANSFERIR el concepto en vez de reconocer un patrón que ya ha memorizado. Lo que no cambia es la demanda cognitiva: el objetivo y su exigencia vienen fijados por las secciones anteriores.

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


# ── PERFIL DE CONTENIDO ───────────────────────────────────────────────────────


CONTENT_PROFILE_FIELD_NAMING = """\
- CLAVES EN INGLÉS (INNEGOCIABLE): los nombres de campo — las claves del objeto `fields` — van SIEMPRE en inglés, en snake_case y en ASCII puro; cada uno debe casar con `^[a-z][a-z0-9_]*$` (sin acentos, sin ñ, sin espacios, sin mayúsculas, sin guiones). Es la ÚNICA parte del perfil que no va en el idioma del material: `description`, `guidance`, `general_generation_rules` y `content_context` sí van en ese idioma. Traduce el ROL del campo, no transcribas su etiqueta: «enunciado» → `statement`, «solución» → `solution`, «nivel de dificultad» → `difficulty_level`.
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


CONTENT_PROFILE_SCHEMA_GRAMMAR = """\
`schema` es SIEMPRE un objeto JSON. Nunca una lista, nunca una cadena suelta. TODAS sus claves van DENTRO de ese objeto; ninguna como hermana de `schema`. Vocabulario permitido, y ninguno más:
- `"type"`: uno de `"string"`, `"integer"`, `"number"`, `"boolean"`, `"array"`, `"object"`.
- `"type"` como LISTA de esos mismos nombres, para valores que admiten ausencia: {"type": ["string", "null"]}. Dentro de `type` todo son NOMBRES DE TIPO entrecomillados, `"null"` incluido.
- con `"type": "array"`, la clave `"items"` va DENTRO del schema: {"type": "array", "items": {"type": "string"}}.
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


def infer_content_profile_prompt(sample: str) -> str:
    return f"""\
Analiza una muestra representativa del material docente en bruto de una asignatura (ejercicios, problemas, actividades, preguntas) y deduce el PERFIL DE CONTENIDO que describe su estructura. El perfil define, de forma abstracta, la anatomía de un ejercicio de esta asignatura: qué campos lo componen, de qué tipo son, cómo se extraen de un documento y cómo se redactaría uno nuevo.

El perfil es la ÚNICA pieza que instancia el sistema para una asignatura concreta: el mismo motor genera ejercicios de programación, problemas de física, preguntas de test o supuestos prácticos, pero siempre material de aprendizaje. Describe lo que la muestra TIENE, con nombres de campo que seguirían teniendo sentido en cualquier otra asignatura; no eleves a estructura lo que es una peculiaridad de maquetación de estos documentos.

La muestra puede provenir de varios documentos distintos, separados por líneas `===== DOCUMENTO: ... =====`. Deduce la estructura COMÚN a todos, no la de uno solo.

# QUÉ DEBES PRODUCIR
Un único objeto JSON con EXACTAMENTE estas claves de nivel superior:

{{
  "content_context": {{ "<clave>": "<valor>" }},
  "general_generation_rules": ["<regla>", "..."],
  "primary_field": "<nombre de uno de los campos>",
  "fields": {{
    "<field_name>": {{
      "schema": {{ "type": "string" }},
      "description": "...",
      "guidance": {{ "extraction": "...", "generation": "..." }}
    }}
  }}
}}

# content_context
Metadatos docentes de la asignatura, inferidos de la muestra. Objeto de pares clave→valor de texto. Aguas abajo, TODOS los prompts del sistema leen este bloque para fijar el registro, el nivel de exigencia y el idioma de lo que redactan, así que es lo que sitúa la asignatura entera. Usa estas claves canónicas cuando puedas deducir su valor con seguridad — `subject` (materia o asignatura), `educational_level` (etapa o curso: secundaria, primer curso de grado…), `language_of_instruction` (idioma de instrucción) — y añade las que la materia exija (p. ej. `programming_language`). Incluye solo lo que deduzcas con seguridad; nada inventado.

# fields — CÓMO SE LLAMAN
{CONTENT_PROFILE_FIELD_NAMING}

# fields — CUÁLES INCLUIR
Un campo por cada pieza de información ESENCIAL que compone un ejercicio.

- MENOS ES MÁS: incluye el conjunto MÍNIMO de campos que capture por completo un ejercicio. Cada campo debe ganarse su sitio: NO añadas campos especulativos, redundantes, derivables de otros ni presentes solo de forma anecdótica en la muestra. Al mismo tiempo, NO omitas nada esencial para representar o redactar el ejercicio (como mínimo, el que porta la carga semántica principal). Ante la duda entre añadir un campo marginal o dejarlo fuera, déjalo fuera. Lo habitual son 3-5 campos.
- PRUEBA DE DERIVABILIDAD (aplícala a CADA campo antes de incluirlo): si su valor puede calcularse a partir de los demás campos sin volver a mirar el documento, NO es un campo — se deduce, y sobra. Descarta en particular: banderas que solo indican si otro campo tiene valor o está vacío (`is_solved`, `has_solution`: eso ya lo dice que `solution` sea null); contadores, longitudes o tamaños de otro campo; y campos cuyo valor sea una reformulación de otro. Si al describir un campo necesitas mencionar otro campo para definirlo, es señal casi segura de que es derivable.
- NADA DE CONCEPTOS NI TEMAS: no declares campos de conceptos, temas, materia o etiquetas temáticas (`topic_tags`, `concepts`, `keywords`, `subject`…). Qué concepto del currículo practica cada ejercicio lo anota el sistema aguas abajo contra un grafo de conocimiento, y un campo así se solaparía con esa anotación. Lo que sitúe a la asignatura entera (materia, nivel educativo, idioma) va en `content_context`, no en `fields`.
- COBERTURA MÍNIMA: el perfil debe bastar para (a) representar el ejercicio, (b) recuperarlo semánticamente y (c) redactar uno nuevo PARAMETRIZADO. En la práctica eso casi siempre exige: el enunciado que porta la carga semántica (el `primary_field`, obligatorio); la solución esperada, cuando el material la trae o la admite; y al menos un campo CLASIFICATORIO que un docente pueda fijar como parámetro al encargar un ejercicio nuevo (dificultad, nivel, modalidad…). Si la muestra no etiqueta ese eje clasificatorio pero es deducible observando el ejercicio, decláralo igualmente y define el criterio (ver POLÍTICA DE NULOS).

Para cada campo:
- `schema`: la forma del valor.
{CONTENT_PROFILE_SCHEMA_GRAMMAR}
- `description`: la NATURALEZA intrínseca del campo (qué representa), en el idioma de instrucción de la asignatura.
- `guidance.extraction`: cómo EXTRAER este campo de un documento fuente. **Redáctala con más detalle y precisión que el resto de textos**: alimenta un proceso de extracción posterior que debe ser exacto y determinista, así que sé concreto y accionable. Cubre, cuando apliquen: qué copiar y si va LITERAL o normalizado; los LÍMITES con los campos vecinos (qué pertenece a este campo y qué NO, para que no se solapen); los marcadores o encabezados concretos del documento que lo delimitan (p. ej. "Solución:", "Ejercicios propuestos"); qué EXCLUIR (etiquetas de enumeración, cabeceras de sección, artefactos de página); y, solo en campos que admitan ausencia según la POLÍTICA DE NULOS, cuándo el campo va a null. Aplica a todo campo que pueda localizarse en el material.
- `guidance.generation`: cómo REDACTAR este campo al crear un ejercicio nuevo desde cero. **Inclúyela SOLO si el campo se redacta de verdad** (ver criterio abajo); si no, omítela y deja en `guidance` únicamente `extraction`.

# POLÍTICA DE NULOS — `null` ES EL ÚLTIMO RECURSO
Un campo admite `null` SOLO cuando el contenido que representa PUEDE NO EXISTIR en el ejercicio (p. ej. la solución de un ejercicio que se plantea sin resolver). Que el documento no lo ETIQUETE explícitamente NO es motivo para admitir `null`: es motivo para definir un criterio que permita DEDUCIRLO del propio contenido.

Por tanto, para todo campo CLASIFICATORIO (nivel, categoría, tipo, modalidad…):
- NO lo declares opcional por defecto. Si su valor es deducible observando el ejercicio, el campo NO lleva `null`.
- Su `description` debe incluir un CRITERIO INTERNO DE CLASIFICACIÓN propio de la asignatura: enumera cada valor posible junto a las SEÑALES OBSERVABLES que lo identifican (qué construcciones, qué complejidad, qué exigencia o qué conocimientos previos supone el ejercicio). El criterio debe cubrir TODO el material, de modo que cualquier ejercicio pueda clasificarse sin excepción.
- Su `guidance.extraction` debe decir: si el documento trae una etiqueta explícita, se usa esa; si NO la trae, se aplica al contenido del ejercicio el criterio definido en `description`. NUNCA "si no hay etiqueta, null".

# QUÉ CAMPOS LLEVAN guidance.generation (SENTIDO COMÚN)
No todos los campos se redactan; muchos son de ENTRADA, no de salida. Clasifica cada campo:
- CONTENIDO REDACTADO — su valor es lo que se escribe al crear un ejercicio nuevo desde cero (el enunciado, la solución). → `guidance` con `extraction` Y `generation`.
- ENTRADA / CONTROL / METADATO — su valor NO se redacta: lo DECIDE de antemano el docente que encarga el ejercicio (un nivel de dificultad objetivo, una modalidad), es una etiqueta o clasificación, o solo tiene sentido al leer un documento ya existente (identificadores, procedencia, referencia al documento origen). → `guidance` con SOLO `extraction`; OMITE `generation`.

Prueba rápida: al encargar un ejercicio nuevo, ¿un docente FIJARÍA este valor como parámetro de entrada, o es una etiqueta/clasificación? → NO lleva `guidance.generation`. ¿Se REDACTA como parte del ejercicio creado? → SÍ la lleva. El `primary_field` es siempre contenido redactado: lleva `guidance.generation`.

# primary_field
El nombre del campo que porta la CARGA SEMÁNTICA principal del ejercicio: el enunciado, el texto que plantea la tarea al alumno. Aguas abajo es lo que se compara contra el grafo del currículo para decidir qué concepto practica cada ejercicio, así que debe ser el campo que un docente leería para saber de qué va. Debe ser uno de los campos declarados en `fields`.

# general_generation_rules
Reglas generales, transversales a todos los campos, que debería respetar la redacción de ejercicios nuevos: convenciones de estilo, notación, formato o alcance que observes de forma consistente en el material docente de la muestra. Describe cómo escribe ESTA asignatura, no buenas prácticas didácticas genéricas — de la calidad pedagógica ya se ocupa el generador. Propón las que se deduzcan razonablemente del material; es un borrador que un docente revisará.

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Los nombres de campo (claves de `fields`) SIEMPRE en inglés y snake_case. El resto de texto de cara al humano (`description`, `guidance`, `general_generation_rules`, `content_context`) en el idioma del material de la muestra.
- Incluye solo los campos ESENCIALES: menos es más, pero sin dejar fuera nada imprescindible. Ninguno derivable de otro. `null` únicamente donde el contenido pueda no existir.
- Cada valor de texto en UNA SOLA LÍNEA: sin saltos de línea reales, sin backticks ni bloques de código dentro de los strings. Escapa saltos (`\\n`) y comillas internas (`\\"`).
- ANTES DE RESPONDER, verifica las tres cosas que más fallan: (1) el valor de cada `schema` es un OBJETO `{{...}}`, nunca una lista; (2) cada clave de `fields` casa con `^[a-z][a-z0-9_]*$`; (3) `primary_field` es exactamente una de esas claves.

<<<MUESTRA>>>
{sample}
<<<FIN>>>

JSON:"""


def repair_content_profile_prompt(profile: str, error_msg: str) -> str:
    return f"""\
El siguiente PERFIL DE CONTENIDO parsea como JSON válido pero no cumple el formato exigido. Corrígelo.

# ERROR DE VALIDACIÓN
{error_msg}

# PERFIL A CORREGIR
{profile}

# FORMATO DE `schema` — causa habitual del error
{CONTENT_PROFILE_SCHEMA_GRAMMAR}

# NOMBRES DE CAMPO
{CONTENT_PROFILE_FIELD_NAMING}

# REGLAS
- Conserva el contenido original (`description`, `guidance`, reglas, contexto) tal cual; corrige SOLO lo que incumple el formato. Si renombras un campo, renómbralo también donde se le referencie.
- Claves de nivel superior exactamente: `content_context`, `general_generation_rules`, `primary_field`, `fields`.
- `primary_field` debe ser una de las claves de `fields`.
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después. Sin backticks, sin comentarios, sin explicaciones.

JSON:"""