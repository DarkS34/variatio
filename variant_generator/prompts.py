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
        context_block = f"\n# CONTEXTO DEL DOCUMENTO\n{context_lines}\n"

    field_guidance_section = ""
    if field_guidance_block.strip():
        field_guidance_section = (
            "\n# GUÍA DE EXTRACCIÓN POR CAMPO\n"
            "Instrucciones específicas sobre QUÉ extraer y CÓMO formatearlo en cada campo. Síguelas literalmente:\n"
            f"{field_guidance_block}\n"
        )

    return f"""\
Extrae elementos estructurados de un fragmento markdown pre-segmentado.

El input contiene uno o varios elementos. Si hay varios, vienen separados por líneas `---`. Cada bloque entre separadores (o el input completo si es un único bloque) representa exactamente UN elemento. Dentro de un bloque, todo lo que encuentres — sub-preguntas, apartados (a/b/c, i/ii/iii), bloques de código embebidos, instrucciones de seguimiento, párrafos explicativos, tablas, ejemplos — pertenece a ese único elemento.

Produce un JSON array con un objeto por elemento, conforme al schema de abajo.

# SCHEMA DE SALIDA
Cada objeto del array debe cumplir este JSON Schema. El campo `description` de cada propiedad describe la NATURALEZA del campo (qué representa). Para esta tarea de extracción, sigue además las instrucciones específicas que aparecen en «GUÍA DE EXTRACCIÓN POR CAMPO» más abajo.

{schema}
{field_guidance_section}
# REGLAS DE EXTRACCIÓN
- Copia los valores literalmente del texto fuente. No reescribas, no traduzcas, no resumas, no inventes contenido.
- Si un campo admite null y el contenido no aparece en la fuente, ponlo a null. Nunca fabriques contenido para rellenar.
- Elimina marcadores de enumeración inicial (`1.`, `2)`, `Ejercicio 3:`, `Exercise 4.`, `Problema 5 -`, `Apartado 6:`, `Sección 7 –`, etc.) en los campos de texto. Los valores deben empezar con el primer carácter real del contenido, no con un número o etiqueta.
- Para strings multilínea (código, prosa con párrafos): escapa saltos como `\\n` y comillas internas como `\\"`.
- Respeta los constraints del schema (`minLength`, `maxLength`, `pattern`, etc.).

# REGLAS DE SALIDA
- Un único JSON array. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios.
- Si no hay elementos extraíbles del input, devuelve `[]`.
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
        context_block = f"\n# CONTEXTO\n{context_lines}\n"

    relations_block = ""
    relations_with_neighbors = {v: ns for v, ns in relations.items() if ns}
    if relations_with_neighbors:
        relations_lines = "\n".join(
            f"- {verbose}: {', '.join(neighbors)}."
            for verbose, neighbors in relations_with_neighbors.items()
        )
        relations_block = f"\n# RELACIONES ENTRE CONCEPTOS\n{relations_lines}\n"

    siblings_block = ""
    if siblings:
        siblings_block = (
            f"\n# OTROS CONCEPTOS DEL MISMO DOMINIO\n{', '.join(siblings)}\n"
        )

    return f"""\
Estás generando una descripción para el concepto «{concept}» del dominio «{domain}».
{context_block}{relations_block}{siblings_block}
# OBJETIVO
Esta descripción se usará para recuperar semánticamente este concepto a partir del texto principal de los items de contenido del dominio (lo que cada item plantea, describe, pregunta o ejemplifica). Debe LEER COMO uno de esos textos, o como la introducción a uno, no como definición académica de manual.

# DISTINTIVIDAD (CRÍTICO)
- La descripción debe encajar SOLO con items que enseñen este concepto en concreto, no con cualquier item del dominio.
- Evita vocabulario universal del dominio — palabras y giros que aparecerían naturalmente en items de muchos conceptos distintos. Identifica qué léxico es transversal en este dominio (lo que usarías para describir el dominio en general, o para describir cualquiera de los "otros conceptos del mismo dominio") y NO lo uses.
- No uses ejemplos concretos genéricos: placeholders típicos, datos de relleno o escenarios neutros que aparezcan en items de varios conceptos diferentes. Si das un ejemplo, que sea uno cuyo enunciado SOLO tendría sentido si el concepto central fuera este.
- Para conceptos paraguas o troncales con pocos detalles propios, prefiere una descripción MUY CORTA y sobria que mencione únicamente lo que los distingue de los hermanos del dominio. Mejor 1 frase específica que 4 frases genéricas.
- Si lo que has escrito también describiría a un hermano del dominio, REESCRÍBELO o RECÓRTALO hasta que no.

# REGLAS DE FORMA
- 1-4 frases, según haga falta para ser específico sin caer en lo genérico.
- Estilo "tipo de item que ejemplifica, aplica o practica este concepto", no definición formal.
- Apóyate en contexto y relaciones para inferir el registro y vocabulario de superficie del dominio — términos, símbolos, sintaxis, fórmulas, identificadores o construcciones propias que aparecerían naturalmente en items reales de esa temática y nivel. Lo que no aplique al dominio, no lo uses.
- Idioma: el natural del dominio descrito en el contexto. Si no se desprende con claridad, usa el mismo idioma de los nombres de los conceptos.
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
        context_block = f"\n# CONTEXTO\n{context_lines}\n"

    relations_block = ""
    if relations.strip():
        relations_block = (
            "\n# RELACIONES ENTRE LOS CANDIDATOS\n"
            "Relaciones del grafo de conocimiento entre los propios candidatos. Úsalas para elegir el NIVEL DE ESPECIFICIDAD correcto:\n"
            f"{relations}\n"
        )

    return f"""\
Clasifica el siguiente item de contenido educativo asignándole los conceptos del currículo que trabaja.
{context_block}
# CONCEPTOS CANDIDATOS
Ordenados de mayor a menor relevancia semántica respecto al texto del item. Bajo cada nombre está la descripción del concepto: describe qué clase de item lo ejemplifica o practica. Juzga por la descripción, no por el nombre.
{candidates}
{relations_block}
# ESQUEMA DE SALIDA
{{
  "concepts": ["Concepto A", "Concepto B"],
  "primary_concept": "Concepto A"
}}

# REGLAS
- Usa ÚNICAMENTE conceptos de la lista de candidatos. No inventes ni parafrasees nombres.
- `concepts`: lista de todos los conceptos que el item trabaja de forma explícita o necesaria.
- `primary_concept`: el concepto central que el item pretende practicar. Debe aparecer también en `concepts`.
- ESPECIFICIDAD: elige como `primary_concept` el concepto MÁS ESPECÍFICO que el item practique de verdad. Si un candidato es un tipo de otro, o parte de otro, y el item trabaja el específico, el específico es el primario; incluye el general en `concepts` solo si el item lo trabaja además por sí mismo.
- El orden de los candidatos es una pista, no una respuesta: el primero no tiene por qué ser el primario.
- Si el item trabaja claramente un solo concepto, `concepts` tendrá un único elemento.
- Si tras analizar los candidatos consideras que NINGUNO representa lo que el item practica de forma central, devuelve {{"concepts": [], "primary_concept": null}}. Usa esta opción con criterio: solo cuando ningún candidato describa el contenido real del item, no ante mera incertidumbre.
- Responde SOLO con el JSON. Sin texto antes ni después, sin backticks, sin comentarios.

# ITEM
{statement}

JSON:"""


# ── GENERACIÓN DE CONTENIDO ──────────────────────────────────────────────────


def generate_content_prompt(
    context: dict,
    target_concepts_block: str,
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
        or "(Ningún ejemplo disponible — genera el item de cero respetando las reglas anteriores.)"
    )

    already_block = ""
    if already_generated:
        existing_lines = "\n".join(f"- {s.strip()[:240]}" for s in already_generated)
        already_block = (
            "\n# YA GENERADOS EN ESTE LOTE — NO REPITAS LA TEMÁTICA NI EL ESCENARIO\n"
            f"{existing_lines}\n"
        )

    curriculum_section = ""
    if curriculum_block.strip():
        curriculum_section = (
            "\n# CURRÍCULO DEL ALUMNO (RESTRICCIÓN DURA)\n"
            "El item NO puede introducir conceptos fuera de esta lista. Los conceptos objetivo son un subconjunto de este currículo:\n"
            f"{curriculum_block}\n"
        )

    return f"""\
Genera UN nuevo elemento de contenido conforme al schema indicado abajo.

# CONTEXTO
{context_lines}

# CONCEPTOS OBJETIVO
El item debe practicar estos conceptos del currículo y no introducir otros más avanzados:
{target_concepts_block}
{curriculum_section}
# VALORES FIJOS PARA ESTA GENERACIÓN
Algunos campos del schema ya tienen su valor decidido por el orquestador. Respétalos exactamente:
{fixed_values_block}

# REGLAS DE GENERACIÓN
{rules_block}

# CREATIVIDAD DE TEMÁTICA
La temática (cover story / contexto narrativo) debe ser ORIGINAL y CREATIVA. Inventa un dominio narrativo concreto: logística, biología, juegos, finanzas, geografía, deportes, cocina, música, viajes, e-commerce, agricultura, astronomía, transporte, redes sociales, salud, arte... cualquier ámbito reconocible. NO reutilices ámbitos ya cubiertos en los ejemplos de referencia ni en los items previos del lote. La sustancia (qué se trabaja) viene fijada por las secciones anteriores; lo que cambia entre items es el envoltorio narrativo.

# EJEMPLOS DE REFERENCIA
Los siguientes items trabajan conceptos relacionados. Úsalos como referencia de FORMA, REGISTRO Y EXTENSIÓN. NO copies su temática, ni su estructura literal, ni reutilices sus escenarios.
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


def infer_content_profile_prompt(sample: str) -> str:
    return f"""\
Analiza una muestra representativa de materiales educativos en bruto (ejercicios, problemas, actividades) y deduce el PERFIL DE CONTENIDO que describe su estructura. El perfil define, de forma abstracta, la forma de cada elemento de contenido del dominio: qué campos lo componen, de qué tipo son, cómo se extraen de un documento y cómo se generaría uno nuevo.

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
Metadatos del dominio inferidos de la muestra (p. ej. materia/asignatura, nivel educativo, idioma, lenguaje de programación si aplica). Objeto de pares clave→valor de texto. Incluye solo lo que deduzcas con seguridad.

# fields
Un campo por cada pieza de información ESENCIAL que compone un elemento.

- CLAVES EN INGLÉS: los nombres de campo (las claves del objeto `fields`) van SIEMPRE en inglés y en snake_case (p. ej. `statement`, `solution`, `difficulty_level`), aunque el material esté en otro idioma. Es la ÚNICA parte que no va en el idioma del dominio; el resto de textos (`description`, `guidance`…) sí.
- MENOS ES MÁS: incluye el conjunto MÍNIMO de campos que capture por completo un elemento. Cada campo debe ganarse su sitio: NO añadas campos especulativos, redundantes, derivables de otros ni presentes solo de forma anecdótica en la muestra. Al mismo tiempo, NO omitas nada esencial para representar o generar el elemento (como mínimo, el que porta la carga semántica principal). Ante la duda entre añadir un campo marginal o dejarlo fuera, déjalo fuera.
- PRUEBA DE DERIVABILIDAD (aplícala a CADA campo antes de incluirlo): si su valor puede calcularse a partir de los demás campos sin volver a mirar el documento, NO es un campo — se deduce, y sobra. Descarta en particular: banderas que solo indican si otro campo tiene valor o está vacío; contadores, longitudes o tamaños de otro campo; y campos cuyo valor sea una reformulación de otro. Si al describir un campo necesitas mencionar otro campo para definirlo, es señal casi segura de que es derivable.

Para cada campo:
- `schema`: la forma del valor. Usa ÚNICAMENTE este vocabulario:
  · `"type"`: uno de "string", "integer", "number", "boolean", "null"; o "array" (con `"items"`); o una LISTA de tipos para valores opcionales (p. ej. `["string", "null"]`).
  · o bien `"enum"`: lista no vacía de valores permitidos (para campos categóricos, p. ej. una dificultad `[1, 2, 3, 4]`). Los elementos de `enum` son VALORES literales, no nombres de tipo. SOLO si el campo admite ausencia según la POLÍTICA DE NULOS, incluye el literal JSON `null` (p. ej. `["básico", "avanzado", null]`), NUNCA la cadena `"null"` — esa sería el texto "null" y haría fallar la validación cuando el valor real sea nulo.
  · restricciones opcionales: `"minLength"`/`"maxLength"` (strings), `"minimum"`/`"maximum"` (números), `"default"` (valor por defecto si el campo es opcional).
  No uses ningún otro tipo ni palabra clave.
- `description`: la NATURALEZA intrínseca del campo (qué representa), en el idioma del dominio.
- `guidance.extraction`: cómo EXTRAER este campo de un documento fuente. **Redáctala con más detalle y precisión que el resto de textos**: alimenta un proceso de extracción posterior que debe ser exacto y determinista, así que sé concreto y accionable. Cubre, cuando apliquen: qué copiar y si va LITERAL o normalizado; los LÍMITES con los campos vecinos (qué pertenece a este campo y qué NO, para que no se solapen); los marcadores o encabezados concretos del documento que lo delimitan (p. ej. "Solución:", "Ejercicios propuestos"); qué EXCLUIR (etiquetas de enumeración, cabeceras de sección, artefactos de página); y, solo en campos que admitan ausencia según la POLÍTICA DE NULOS, cuándo el campo va a null. Aplica a todo campo que pueda localizarse en el material.
- `guidance.generation`: cómo GENERAR este campo al crear un elemento nuevo desde cero. **Inclúyela SOLO si el campo se genera de verdad** (ver criterio abajo); si no, omítela y deja en `guidance` únicamente `extraction`.

# POLÍTICA DE NULOS — `null` ES EL ÚLTIMO RECURSO
Un campo admite `null` SOLO cuando el contenido que representa PUEDE NO EXISTIR en el elemento (p. ej. la solución de un ejercicio que se plantea sin resolver). Que el documento no lo ETIQUETE explícitamente NO es motivo para admitir `null`: es motivo para definir un criterio que permita DEDUCIRLO del propio contenido.

Por tanto, para todo campo CLASIFICATORIO (nivel, categoría, tipo, temática…):
- NO lo declares opcional por defecto. Si su valor es deducible observando el elemento, el campo NO lleva `null`.
- Su `description` debe incluir un CRITERIO INTERNO DE CLASIFICACIÓN propio del dominio: enumera cada valor posible junto a las SEÑALES OBSERVABLES que lo identifican (qué construcciones, qué complejidad, qué requisitos o qué conocimientos previos aparecen en el elemento). El criterio debe cubrir TODO el espacio de elementos, de modo que cualquiera pueda clasificarse sin excepción.
- Su `guidance.extraction` debe decir: si el documento trae una etiqueta explícita, se usa esa; si NO la trae, se aplica al contenido del elemento el criterio definido en `description`. NUNCA "si no hay etiqueta, null".

# QUÉ CAMPOS LLEVAN guidance.generation (SENTIDO COMÚN)
No todos los campos se generan; muchos son de ENTRADA, no de salida. Clasifica cada campo:
- CONTENIDO GENERADO — su valor es la salida creativa que un generador REDACTA al crear un elemento nuevo desde cero (p. ej. el enunciado, el código de la solución). → `guidance` con `extraction` Y `generation`.
- ENTRADA / CONTROL / METADATO — su valor NO se redacta: lo DECIDE de antemano el orquestador como parámetro (un nivel de dificultad objetivo, una categoría, un tipo), es una etiqueta/clasificación, o solo tiene sentido al leer un documento ya existente (identificadores, procedencia, referencia al documento origen). → `guidance` con SOLO `extraction`; OMITE `generation`.

Prueba rápida: al generar un elemento nuevo, ¿un orquestador FIJARÍA este valor como parámetro de entrada, o es un flag/etiqueta/clasificación? → NO lleva `guidance.generation`. ¿El generador lo REDACTARÍA como parte del contenido creado? → SÍ la lleva. El `primary_field` es siempre contenido generado: lleva `guidance.generation`.

# primary_field
El nombre del campo que porta la CARGA SEMÁNTICA principal del elemento: el texto que plantea el problema o la tarea. Se usará aguas abajo para embeddings y etiquetado de conceptos. Debe ser uno de los campos declarados en `fields`.

# general_generation_rules
Reglas generales, transversales a todos los campos, que debería respetar la generación de nuevos elementos (restricciones de contenido, estilo o alcance que observes en la muestra). Propón las que se deduzcan razonablemente del material; es un borrador que un humano revisará.

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Los nombres de campo (claves de `fields`) SIEMPRE en inglés y snake_case. El resto de texto de cara al humano (`description`, `guidance`, `general_generation_rules`, `content_context`) en el idioma del material de la muestra.
- Incluye solo los campos ESENCIALES: menos es más, pero sin dejar fuera nada imprescindible. Ninguno derivable de otro. `null` únicamente donde el contenido pueda no existir.
- Escapa saltos de línea (`\\n`) y comillas internas (`\\"`) dentro de strings.

<<<MUESTRA>>>
{sample}
<<<FIN>>>

JSON:"""