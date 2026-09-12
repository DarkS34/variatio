"""The calls that build a knowledge graph, from one chunk of corpus to the whole syllabus.

The JSON keys they draw — `concepts`, `relations`, `merges`, `canonical`, `aliases`, `drop`,
`domains`, `non_taggable` — are English in both sets: they are the grammar `schemas.py` pins
and what the parsers read, so a translated key yields a well-formed answer that parses to
nothing. The two slots of a triple are ORIGEN and DESTINO in this set's prose and must match
the words `relations.py` puts in the catalogue. The rule blocks below are shared so eight
prompts cannot describe one block format in eight ways.
"""

_KG_LANGUAGE_RULE = """\
# IDIOMA
Escribe el nombre de cada concepto EN EL MISMO IDIOMA que el material de origen. No lo traduzcas, no lo normalices a otro idioma, no lo transliteres. Conserva la redacción, los acentos y las mayúsculas de la terminología de la asignatura.
Las claves de los tipos de relación que se listan abajo son IDENTIFICADORES FIJOS, no palabras del texto: emítelas exactamente como están escritas, sea cual sea el idioma del material."""


def _kg_type_preference_rule(schema) -> str:
    """Render how to choose a relation type, which turns on the schema having a fallback.

    With no catch-all relation the instruction is to emit nothing when no type clearly
    applies; with one it is to prefer the specific types and not to treat the fallback as a
    default drawer.
    """
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
    """Ask one chunk of corpus for its concepts and the typed relations among them.

    The answer is `concepts`, each with a one-sentence definition, and `relations` as
    [source, type, target] triples whose two endpoints both appear in `concepts`. One call
    per chunk and hundreds per corpus, and the results are merged BY NAME — which is why the
    naming canon is the longest section of the prompt: two chunks naming one idea differently
    produce two concepts that never reconcile. `location` is the heading path of the section
    the chunk came from, so neighbouring chunks name things as this part of the syllabus does.
    """
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


def glean_typed_graph_prompt(
    source_text: str,
    schema,
    location: str,
    concepts: list[str],
    definitions: dict[str, str],
    relations: list[list[str]],
) -> str:
    """Ask a SECOND reading of the same chunk for what the first one left out.

    Shown the inventory the first pass wrote, it is asked only for what is missing — the
    "gleaning" pass of GraphRAG and LightRAG — and above all for relations the text supports
    between concepts already named. Its answer is merged into the first and never replaces
    it: `concepts` carries only the new ones, while `relations` may name anything known.
    """
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
- Prefiere que AMBOS extremos sean cosas que se le enseñan a un alumno y de las que se le podría examinar. La extracción recogió también herramientas, notación y vocabulario del documento; un orden colgado de eso describe el material y no el temario, y nada aguas abajo puede usarlo. Cuando una dependencia sea real pero uno de los extremos sea un término así, busca el concepto enseñado que hay detrás y relaciona ese."""


_KG_MATERIAL_ORDER_RULE = """\
# EL ORDEN DE LA LISTA ES EL ORDEN DEL MATERIAL
Los conceptos se listan en el ORDEN EN QUE EL MATERIAL LOS INTRODUCE, de principio a fin del corpus. Quien escribió el material ya decidió un orden de enseñanza, y ese orden es la mejor evidencia que tienes:
- Un concepto se apoya, casi siempre, en conceptos que van ANTES que él en la lista. Para cada uno, mira hacia arriba y pregúntate cuáles de los anteriores tiene que saber ya un alumno.
- Proponer que un concepto se apoye en otro que va DESPUÉS en la lista es afirmar que el material lo enseña en el orden equivocado. Puede ser cierto — un manual a veces adelanta una consecuencia —, pero exige que la dependencia sea inequívoca; ante la duda, respeta el orden del material.
- La distancia en la lista no es un obstáculo: lo primero del corpus es el cimiento de casi todo lo que viene después, y esas dependencias largas son justo las que faltan.
- Cada concepto lleva, cuando se conoce, una definición de una frase tomada del material. Juzga la dependencia sobre la definición, no sobre el parecido de los nombres."""


def link_domain_relations_prompt(domain: str, nodes_block: str, schema) -> str:
    """Ask for the relations MISSING between the concepts of one syllabus block.

    Chunk-by-chunk extraction only sees a dependency when two concepts are explained
    together, which is exactly when the material need not state it, so the teaching order is
    almost entirely absent and recovering it is the main reason this step exists. The
    concepts arrive in the order the material introduces them, which is the evidence the
    prompt leans on. The answer is `relations` alone, as triples over the names listed, and
    `{"relations": []}` when nothing is missing.
    """
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
    """Ask only for the relations that CROSS from one syllabus block to another.

    The scaffolding that orders the syllabus as a whole, which no reading of a single block
    could reveal: a relation between two concepts of the same block is discarded. The blocks
    arrive in the order the material presents them, and so do the concepts inside each. The
    answer is `relations` alone, as triples over the names listed.
    """
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
    """Ask, inside each small group of look-alike names, which of them are ONE concept.

    The groups were formed by name similarity alone, which is a suspicion and not a verdict,
    so many of them merge nothing. The test is the glossary's: one entry or two? The answer
    is `merges`, each entry a `canonical` copied from its own group plus its `aliases`, and
    never names from two groups in one entry. Over-merging costs more than under-merging,
    because a concept lost in a merge is not recovered afterwards.
    """
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
- Cuando un nombre lleve detrás de « — » una definición tomada del material, léela como evidencia de QUÉ idea nombra, no como prueba de que sea otro concepto: cada fragmento definió lo suyo con sus propias palabras, así que dos redacciones distintas de UNA idea son lo normal y son un solo concepto; son dos conceptos solo cuando definen ideas de las que un alumno podría examinarse por separado, por mucho que los nombres se parezcan.
- Una variante gramatical del mismo nombre —singular y plural («Casos de uso» y «Caso de uso»), mayúsculas, un artículo o una preposición de más— es SIEMPRE un solo concepto, digan lo que digan las definiciones que las acompañen.
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
    """Ask which extracted nodes do not name a concept at all, so they can be dropped.

    Extraction is noisy: document metadata, incidental example scenarios and sentence
    fragments come out beside the subject's concepts. The only question asked here is whether
    the string NAMES something — whether what it names works as a LABEL for exercises is the
    taggability review's, later and with the exemplars profile in hand. The answer is `drop`,
    a map from an exact node name to a reason of ten words at most; the unlisted stay.
    """
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


def segment_syllabus_prompt(outline_block: str) -> str:
    """Ask which headings of the corpus open a teaching unit, and what each unit is called.

    The answer is `units`, each with a `name` and the `opens_at` line number of the heading
    that opens it — between 3 and 12 of them, since more than that is splitting by section
    rather than by unit. Everything from one opening heading to the next belongs to that
    unit, which is why only the start is asked for. The outline arrives in the material's own
    order and the result is sorted by `opens_at`, so any reordering attempted is discarded.
    """
    return f"""\
Se te da el ÍNDICE de un corpus de material docente de una sola asignatura: todos sus encabezados, en el orden exacto en que aparecen en el material y numerados desde 1.

Tu tarea: decir qué encabezados ABREN una UNIDAD DIDÁCTICA — un tema, un módulo, un bloque grande del temario — y cómo se llama cada una.

# QUÉ ES UNA UNIDAD
- Es un divisor GRANDE del contenido: lo que el docente llamaría tema, módulo o bloque. No es un apartado, ni un ejemplo, ni un ejercicio, ni una subsección.
- Un encabezado que ya lleva un ordinal en el nombre («Tema I», «Unidad 3», «Módulo II») casi siempre abre una, y es la señal más fiable que hay en el índice.
- POCAS: entre 3 y 12 en total. Si estás nombrando más de una docena, estás partiendo por apartados y no por temas.
- La portada, el índice, la bibliografía, los agradecimientos, los anexos y las notas de la asignatura NO abren unidad.

# EL ORDEN ES EL QUE SE TE DA
- El índice ya viene en el orden del material, que es el orden en que se imparte. NO lo reordenes, no lo reorganices por dificultad y no lo agrupes por afinidad temática. Tu salida se ordena por `opens_at`, así que cualquier reordenación que intentes se descarta.
- Todo lo que va desde el encabezado que abre una unidad hasta el que abre la siguiente PERTENECE a esa unidad. Por eso solo hace falta decir dónde empieza cada una.

# NOMBRES
- El nombre de la unidad puede ser el propio encabezado, limpio: sin el ordinal, sin dos puntos ni guiones sueltos al final. Si el encabezado no dice de qué trata, escribe tú un nombre corto y descriptivo, EN EL MISMO IDIOMA que el índice.
- No repitas un nombre y no escribas dos nombres para el mismo bloque.
- PROHIBIDO un nombre genérico de descarte del tipo «Otros», «Varios», «Miscelánea» o «Sin clasificar»: todo lo que hay entre dos unidades ya pertenece a la primera.

# SALIDA
Un único objeto JSON exactamente con esta forma:
{{
  "units": [{{"name": "<nombre de la unidad>", "opens_at": <número de línea del índice>}}, "..."]
}}
- `opens_at` es el NÚMERO que lleva delante el encabezado en el índice de abajo. No inventes números y no escribas el encabezado en su lugar.
- Nada de texto antes ni después, sin backticks, sin comentarios.

# ÍNDICE DEL CORPUS
{outline_block}

JSON:"""


def curate_graph_domains_prompt(nodes_block: str, documents_block: str = "") -> str:
    """Ask for the NAMES of the syllabus blocks the subject is made of, and nothing more.

    Placing the concepts is a separate and later question, asked in small batches, so
    anything written here about which concept goes where is discarded. This call sees every
    concept — a syllabus's units cannot be named from a sample — and answers `domains`, a
    handful of strings with no catch-all among them, that name being the leftovers pass's
    own sentinel. `documents_block` offers the corpus's document titles as a starting point,
    because teaching material is already organised by topic.
    """
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


def assign_leftover_concepts_prompt(domains_block: str, nodes_block: str) -> str:
    """Ask for the concepts a domain pass overlooked to be placed in the EXISTING domains.

    Asked to partition several hundred concepts in one turn the model reliably forgets a
    fifth of them however loudly the prompt insists on completeness. Rather than insisting
    harder, the leftovers come back as their own much smaller question with the domain names
    fixed, so this pass cannot invent any. The answer is `domains`, a map from an existing
    name to the concepts placed under it, each concept placed exactly once and into the least
    alien domain when none fits: there is no catch-all to fall into.
    """
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
    """Ask which concepts of ONE domain are useless AS A LABEL and leave the tagging.

    Taggability is not a property of the graph: a concept is useless as a label only relative
    to the shapes of item this instance sets, which is why the modalities and real statements
    from the bank travel with the question. The test is discrimination — could an item have
    this concept as its objective, and would the same label fit items from unrelated parts of
    the syllabus? — and the tie-break is to exclude, because an excluded concept keeps working
    through its relations while a vague label pollutes the whole corpus. The answer is
    `non_taggable`, a map from an exact name to a reason of twelve words at most.
    """
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
- Lenguajes, herramientas, plataformas, bibliotecas, estándares y sus nombres — salvo que la asignatura los tenga como objeto de estudio propio: si un ejercicio de estas modalidades puede TRATAR sobre uno de ellos, y no solo sobre algo hecho con él, es un concepto y se queda.
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
