from ..types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(
        key="builders.transcribe_dpi",
        name="TRANSCRIBE_DPI",
        kind="int",
        default=200,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Transcripción de los ejemplares en bruto a partir de la imagen de cada página. Docling lee
estos PDF como texto y pierde tres cosas a la vez: separa los bloques de código de la
pregunta que los cita, aplana sus saltos de línea y deja caer el color que marca la opción
correcta. Renderizar la página y leerla como imagen recupera las tres.""",
    ),
    Setting(
        key="builders.transcribe_temperature",
        name="TRANSCRIBE_TEMPERATURE",
        kind="float",
        default=0.0,
        group="Constructores",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc="""Transcribir es copiar, no escribir: a la temperatura por defecto de Ollama la misma
página volvió con `a = 99` e `if a < 0 : break` sacados de su `while True:`, lo que cambia
en silencio lo que pide el ejercicio. Fijada a 0 por eso.

Sigue siendo una constante propia en vez de `TEMPERATURE_DETERMINISTIC`, aunque tenga el
mismo valor y por la misma razón: esta forma parte de la huella de la caché de páginas
(`_source_docs/pages.py`), así que cambiarla vuelve a transcribir todas las páginas de
todos los corpus. Unificarlas haría que esa consecuencia siguiera a una edición hecha
pensando en otra cosa.""",
    ),
    Setting(
        key="builders.transcribe_max_retries",
        name="TRANSCRIBE_MAX_RETRIES",
        kind="int",
        default=1,
        group="Constructores",
        impact=Impact.NONE,
        minimum=0,
        doc="""Cuántas veces se reintenta la transcripción de la imagen de una página tras un fallo de
parseo antes de que el constructor renuncie a esa página y recurra a la extracción de
texto de Docling.""",
    ),
    Setting(
        key="builders.transcribe_prompt_version",
        name="TRANSCRIBE_PROMPT_VERSION",
        kind="int",
        default=1,
        group="Constructores",
        impact=Impact.LOCKED,
        editable=False,
        minimum=1,
        doc="""Súbelo al cambiar transcribe_page_prompt: forma parte de la huella de la caché de páginas.

Lo sube quien edita el prompt, no quien mira una pantalla.""",
    ),
    Setting(
        key="builders.exemplars_ocr",
        name="EXEMPLARS_OCR",
        kind="bool",
        default=True,
        group="Constructores",
        impact=Impact.NONE,
        doc="""Solo llega a usarse en el camino de respaldo de Docling (fuentes que no son PDF, o PDF
cuya transcripción falló): páginas escaneadas cuyo texto nunca entró en el PDF.""",
    ),
    Setting(
        key="builders.ep_chunk_size",
        name="EP_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota los caracteres por fragmento cuando el constructor del perfil de ejemplares parte
un documento fuente para escanearlo, de modo que cada llamada quepa en el contexto útil
del modelo.""",
    ),
    Setting(
        key="builders.ep_scan_excerpt_chars",
        name="EP_SCAN_EXCERPT_CHARS",
        kind="int",
        default=400,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántos caracteres del extracto de cada modalidad detectada se conservan: los
suficientes para reconocer la modalidad sin arrastrar el ejemplo entero a cada llamada
posterior.""",
    ),
    Setting(
        key="builders.ep_max_item_types",
        name="EP_MAX_ITEM_TYPES",
        kind="int",
        default=6,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántas modalidades distintas conserva el constructor del perfil tras el escaneo,
para que un corpus ruidoso no fragmente el perfil en modalidades casi duplicadas.""",
    ),
    Setting(
        key="builders.eb_chunk_size",
        name="EB_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota los caracteres por fragmento cuando el constructor del banco de ejemplares agrupa
el markdown de un documento fuente para extraerlo.""",
    ),
    Setting(
        key="builders.kg_chunk_size",
        name="KG_BUILDER_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota los caracteres por fragmento que el constructor del grafo lee de una vez durante
la extracción, limitando cuánto texto tiene que razonar una sola llamada.""",
    ),
    Setting(
        key="builders.kg_max_evidence_relations",
        name="KG_MAX_EVIDENCE_RELATIONS",
        kind="int",
        default=6,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántas ternas de relación se muestran como evidencia de un concepto en los prompts
de limpieza y de asignación de dominios, para que un concepto muy conectado no desplace
al resto del lote.""",
    ),
    Setting(
        key="builders.kg_extract_gleaning_passes",
        name="KG_EXTRACT_GLEANING_PASSES",
        kind="int",
        default=1,
        group="Constructores",
        impact=Impact.NONE,
        minimum=0,
        doc="""Una segunda lectura de cada fragmento, enseñándole al modelo lo que ya encontró y
pidiéndole lo que falta (el «gleaning» de GraphRAG/LightRAG). La primera lectura se
queda corta sobre todo en relaciones entre conceptos que sí nombró; la segunda se detiene
sola en cuanto no añade nada. Es la fase más barata de la construcción (8 % medido), así
que doblarla es asumible; 0 la desactiva.""",
    ),
    Setting(
        key="builders.kg_definition_max_chars",
        name="KG_DEFINITION_MAX_CHARS",
        kind="int",
        default=220,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Una definición de una línea por concepto, escrita en el fragmento que lo introduce y
recortada aquí por si el modelo se extiende; acompaña al nombre en todas las llamadas
posteriores de la construcción.""",
    ),
    Setting(
        key="builders.kg_max_source_passages",
        name="KG_MAX_SOURCE_PASSAGES",
        kind="int",
        default=3,
        group="Constructores",
        impact=Impact.REINDEX,
        minimum=1,
        doc="""El anclaje de cada concepto al corpus: de qué párrafos del material de teoría salió.
Es lo que permite enseñar que un concepto del grafo viene de algo real, y es lo que
`concept_description_prompt` lee para no describir de memoria.

Tres pasajes y no todos: un concepto troncal aparece en veinte fragmentos y los veinte
dicen lo mismo; lo que aporta el tercero ya es repetición, y el fichero pasa de cientos
de KB a unas decenas. 900 caracteres es un párrafo largo con su vecino — lo bastante
para que se lea como material y no como un recorte.""",
    ),
    Setting(
        key="builders.kg_source_passage_chars",
        name="KG_SOURCE_PASSAGE_CHARS",
        kind="int",
        default=900,
        group="Constructores",
        impact=Impact.REINDEX,
        minimum=1,
        doc="""El anclaje de cada concepto al corpus: de qué párrafos del material de teoría salió.
Es lo que permite enseñar que un concepto del grafo viene de algo real, y es lo que
`concept_description_prompt` lee para no describir de memoria.

Tres pasajes y no todos: un concepto troncal aparece en veinte fragmentos y los veinte
dicen lo mismo; lo que aporta el tercero ya es repetición, y el fichero pasa de cientos
de KB a unas decenas. 900 caracteres es un párrafo largo con su vecino — lo bastante
para que se lea como material y no como un recorte.""",
    ),
    Setting(
        key="builders.kg_plural_suffixes",
        name="KG_BUILDER_PLURAL_SUFFIXES",
        kind="list[str]",
        default=["s"],
        group="Constructores",
        impact=Impact.NONE,
        doc="""Sufijos que se quitan al normalizar la clave de un concepto para compararlo en la fusión,
de modo que las menciones en plural y en singular del mismo concepto se reconozcan como
una sola.""",
    ),
    Setting(
        key="builders.kg_merge_qualifier_pattern",
        name="KG_BUILDER_MERGE_QUALIFIER_PATTERN",
        kind="str",
        default=r"\s+en (python|java)\b",
        group="Constructores",
        impact=Impact.NONE,
        doc="""Regex stripped from a concept name before merge comparison so a language-qualified
mention folds into its bare form; fails silently if wrong — without it, «Listas en
Python» stops merging into «Listas».""",
    ),
    Setting(
        key="builders.kg_unclassified_domain",
        name="KG_BUILDER_UNCLASSIFIED_DOMAIN",
        kind="str",
        default="Sin clasificar",
        group="Constructores",
        impact=Impact.NONE,
        doc="""The sentinel domain name reserved for concepts `place_leftovers` could not place
anywhere else; fails silently if wrong — leftovers would land in a domain literally
called `Unclassified` instead of being retried.""",
    ),
    Setting(
        key="builders.kg_max_titles_per_doc",
        name="KG_BUILDER_MAX_TITLES_PER_DOC",
        kind="int",
        default=3,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántos títulos de sección por documento se ofrecen como evidencia al nombrar los
dominios, para que un documento con muchos encabezados no domine esa llamada.""",
    ),
    Setting(
        key="builders.kg_title_ubiquity",
        name="KG_BUILDER_TITLE_UBIQUITY",
        kind="float",
        default=0.6,
        group="Constructores",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=1.0,
        doc="""La fracción de documentos en la que debe aparecer un encabezado para contar como título
de sección recurrente en vez de como uno suelto; alimenta la llamada que nombra los
dominios.""",
    ),
    Setting(
        key="builders.kg_relation_schema",
        name="KG_RELATION_SCHEMA",
        kind="str",
        default="es",
        group="Constructores",
        impact=Impact.LOCKED,
        editable=False,
        doc="""Elige qué vocabulario de relaciones de `relations.py` usa el grafo; fija las etiquetas
verbose en español por las que el cargador indexa el grafo.

Decisión cerrada: debe seguir siendo «es». Las etiquetas verbose son load-bearing y el
grafo que se distribuye las contiene; cambiarlo invalidaría todos los grafos de todos
los workspaces.""",
    ),
    Setting(
        key="builders.kg_merge_similarity",
        name="KG_BUILDER_MERGE_SIMILARITY",
        kind="float",
        default=0.80,
        group="Constructores",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=1.0,
        doc="""El suelo de similitud coseno por encima del cual dos nombres de concepto se proponen a la
llamada de fusión como candidatos a ser el mismo concepto, durante la limpieza del grafo.""",
    ),
    Setting(
        key="builders.kg_max_merge_group",
        name="KG_BUILDER_MAX_MERGE_GROUP",
        kind="int",
        default=8,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps how many candidate concept names can be grouped together for a single merge
decision during graph cleaning, keeping each call's comparison set small enough to judge.""",
    ),
    Setting(
        key="builders.kg_merge_groups_per_call",
        name="KG_BUILDER_MERGE_GROUPS_PER_CALL",
        kind="int",
        default=10,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántos grupos candidatos a fusión se agrupan en una sola llamada de limpieza,
limitando cuánto tiene que decidir el modelo de una vez.""",
    ),
    Setting(
        key="builders.kg_clean_batch_size",
        name="KG_BUILDER_CLEAN_BATCH_SIZE",
        kind="int",
        default=60,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántos conceptos se envían al modelo en un lote durante las pasadas de fusión y
descarte de la fase de limpieza.""",
    ),
    Setting(
        key="builders.kg_domain_batch_size",
        name="KG_BUILDER_DOMAIN_BATCH_SIZE",
        kind="int",
        default=20,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántos conceptos se colocan en dominios en una sola llamada de `assign_round`,
manteniendo cada lote lo bastante pequeño como para juzgarlo bien.""",
    ),
    Setting(
        key="builders.kg_domain_rounds",
        name="KG_BUILDER_DOMAIN_ROUNDS",
        kind="int",
        default=3,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántas veces `place_leftovers` vuelve a pedir al modelo que coloque los conceptos
que dejó sin clasificar, antes de que lo que quede vaya a `KG_BUILDER_UNCLASSIFIED_DOMAIN`.""",
    ),
]
