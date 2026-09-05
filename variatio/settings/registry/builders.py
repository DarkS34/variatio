"""The «Constructores» settings: transcription, chunking and each builder's own knobs."""

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
        doc="""Transcripción del material en bruto a partir de la imagen de cada página, en los dos slots
de `raw/`. Docling lee estos PDF como texto y pierde tres cosas a la vez: separa los bloques
de código de la pregunta que los cita, aplana sus saltos de línea y deja caer el color que
marca la opción correcta. Renderizar la página y leerla como imagen recupera las tres.

Desde el 2026-08-27, por petición explícita del usuario, el corpus del grafo va por esta
misma ruta: los dos slots se transcriben con el mismo motor y el mismo algoritmo, y a
Docling le quedan el `.docx` y el `.pptx`, que no tienen página que renderizar — sus
imágenes se leen aparte, una llamada por imagen, con el mismo modelo y las mismas reglas.
No se renderizan, así que esta resolución no las afecta.""",
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
        doc="""Cuántas veces se reintenta la transcripción de la imagen de una página tras un fallo del
motor antes de que el constructor renuncie a esa página. Cuando renuncia deja en la caché
un marcador de fallo, no un hueco: una página perdida son ejercicios perdidos, y algo con
lo que tropezar es mejor que una página que parece vacía.""",
    ),
    Setting(
        key="builders.transcribe_max_output_tokens",
        name="TRANSCRIBE_MAX_OUTPUT_TOKENS",
        kind="int",
        default=4096,
        group="Constructores",
        impact=Impact.NONE,
        minimum=256,
        doc="""Techo de tokens de SALIDA de la llamada que transcribe una página o una imagen. Sin él
el modelo dispone de todo su presupuesto, y lo gasta: el 2026-09-05, en `compiladores`,
nueve páginas de dos exámenes salieron con exactamente 40.960 tokens cada una — el tope
del motor — porque la línea de puntos donde el alumno escribe su nombre («Nombre: ____»)
se transcribió como una racha de `\\_` que el modelo no supo dónde parar. Cada una costó
0,063 $ y ~65 s en vez de 0,003 $ y ~1 s, y los 738.832 caracteres de basura resultantes
pasaron enteros al perfil y al banco, que gastaron el 80 % de sus llamadas en leerlos:
~1,9 $ de los 5,48 $ de esa construcción, y un examen que aportó 0 ítems.

El valor sale de la medición y no del gusto: de las 537 páginas PDF legítimas de las tres
asignaturas de referencia la más larga son 6.871 caracteres (~1.900 tokens), y en
`compiladores` el p99 son 739 y la mayor sana 1.397 — entre 1.397 y 40.960 no hay ni una.
4.096 deja 2,1× de margen sobre la peor página real y corta la desbocada al 10 % de su
coste. Una respuesta que llega al techo se marca como PÁGINA FALLIDA (`FAILED_PAGE_PREFIX`),
no se guarda truncada: una página cortada en silencio es la pérdida que este proyecto no
acepta, y una marcada sale en rojo en «Apuntes y ejercicios», donde se corrige a mano o se
sube este valor si de verdad era una página larguísima. No se reintenta, porque a
temperatura 0 la misma imagen produce la misma racha.

No forma parte de la huella de la caché: subirlo o bajarlo no vuelve a transcribir nada.""",
    ),
    Setting(
        key="builders.transcribe_seam_chars",
        name="TRANSCRIBE_SEAM_CHARS",
        kind="int",
        default=1200,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuánto se le enseña al modelo de cada lado de una costura: los últimos N caracteres de una
página y los primeros N de la siguiente. Es lo que decide si lo que abre la segunda página
continúa lo que la primera dejó a medias.

1.200 sin medir: es un párrafo largo con su vecino a cada lado, bastante para ver dónde
acaba una frase o si una tabla sigue, y lo bastante corto para que la llamada no cueste
como una lectura del fragmento entero. NO forma parte de la huella de la caché de páginas:
cambiarlo no vuelve a transcribir nada, solo cambia lo que verá la próxima revisión de
costuras.""",
    ),
    Setting(
        key="builders.transcribe_prompt_version",
        name="TRANSCRIBE_PROMPT_VERSION",
        kind="int",
        default=4,
        group="Constructores",
        impact=Impact.LOCKED,
        editable=False,
        minimum=1,
        doc="""Súbelo al cambiar transcribe_page_prompt o transcribe_image_prompt: forma parte de la
huella de la caché de páginas y de la de imágenes, y subirlo caduca las dos.

Lo sube quien edita el prompt, no quien mira una pantalla. 3 desde el 2026-09-02: el bloque
`IMAGE_RULES` que comparten los dos prompts (una imagen se transcribe por lo que contiene y
solo se describe cuando no hay nada que copiar). OJO: `config.json` guarda este valor como
cualquier otro y el fichero gana al registro, así que subirlo aquí sin subirlo también en el
fichero de la instalación no caduca nada. 4 desde el 2026-09-03: el prompt de página pide los
ENCABEZADOS con `#` según la jerarquía visual (sección `# ESTRUCTURA`). Hasta entonces no los
pedía y quedaban al criterio del modelo; con la versión 3 dejó de marcar las portadas de tema
(medido sobre `apuntes.pdf` de `cs0-examenes`, T=0, dos pasadas: v2 marcaba «# Tema I», «# Tema
II» y «# Tema V», v3 solo «# Tema V»), y sin ellos `segment_syllabus` abría las unidades del
grafo por apartados.""",
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
        key="builders.eb_batch_overlap_blocks",
        name="EB_BATCH_OVERLAP_BLOCKS",
        kind="int",
        default=1,
        group="Constructores",
        impact=Impact.NONE,
        minimum=0,
        doc="""Cuántos bloques del final de un lote se arrastran al principio del siguiente cuando el
constructor del banco parte un documento para extraerlo.

El corte es por tamaño, así que un ejercicio a caballo entre dos lotes se veía a medias en
cada llamada y salía extraído dos veces y mal las dos. Con solape el ejercicio entero cabe
en al menos una de las dos llamadas, y los ítems repetidos se descartan comparando su campo
primario normalizado, antes de que consuman un id. Un bloque basta porque los bloques son
los que `split_blocks` reconoce: un ejercicio con sus apartados es uno solo. 0 lo desactiva
y vuelve al corte seco.""",
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
        doc="""Expresión regular que se recorta del nombre de un concepto antes de comparar para
fusionar, de modo que una mención cualificada por lenguaje se pliegue sobre su forma
desnuda; falla en silencio si está mal — sin ella, «Listas en Python» deja de fusionarse
con «Listas».""",
    ),
    Setting(
        key="builders.kg_unclassified_domain",
        name="KG_BUILDER_UNCLASSIFIED_DOMAIN",
        kind="str",
        default="Sin clasificar",
        group="Constructores",
        impact=Impact.NONE,
        doc="""El nombre de dominio centinela reservado para los conceptos que `place_leftovers` no
pudo colocar en ningún otro sitio; falla en silencio si está mal — los sobrantes
aterrizarían en un dominio llamado literalmente `Unclassified` en lugar de reintentarse.""",
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
        doc="""Acota cuántos nombres de concepto candidatos pueden agruparse para una sola decisión de
fusión durante la limpieza del grafo, manteniendo el conjunto que cada llamada compara lo
bastante pequeño como para poder juzgarlo.""",
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
