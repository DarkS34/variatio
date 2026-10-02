"""The "Constructores" settings: transcription, chunking and each builder's own knobs."""

from ..types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(
        key="builders.transcribe_dpi",
        name="TRANSCRIBE_DPI",
        kind="int",
        default=200,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe",
        impact=Impact.NONE,
        minimum=1,
        doc="""Transcripción del material en bruto a partir de la imagen de cada página, en los dos slots
de `raw/`. Docling lee estos PDF como texto y pierde tres cosas a la vez: separa los bloques
de código de la pregunta que los cita, aplana sus saltos de línea y deja caer el color que
marca la opción correcta. Renderizar la página y leerla como imagen recupera las tres.

El corpus del grafo va por esta misma ruta: los dos slots se transcriben con el mismo motor y el mismo algoritmo, y a
Docling le quedan el `.docx` y el `.pptx`, que no tienen página que renderizar — sus
imágenes se leen aparte, una llamada por imagen, con el mismo modelo y las mismas reglas.
No se renderizan, así que esta resolución no las afecta.""",
    ),
    Setting(
        key="builders.transcribe_max_retries",
        name="TRANSCRIBE_MAX_RETRIES",
        kind="int",
        default=1,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe",
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
        stages=("transcription",),
        phase="transcribe",
        impact=Impact.NONE,
        minimum=256,
        doc="""Techo de tokens de SALIDA de la llamada que transcribe una página o una imagen. Sin él el
modelo dispone de todo su presupuesto, y lo gasta: la línea de puntos donde el alumno
escribe su nombre («Nombre: ____») se transcribe como una racha de `\\_` que el modelo no
sabe dónde parar, y una página así consume el tope entero del motor — veinte veces el coste
y sesenta veces el tiempo de una página real, con la basura pasando entera al perfil y al
banco.

El valor sale de la medición y no del gusto: de las 537 páginas PDF legítimas de las tres
asignaturas de referencia la más larga son 6.871 caracteres (~1.900 tokens), y en
`compiladores` el p99 son 739 y la mayor sana 1.397 — entre 1.397 y 40.960 no hay ni una.
4.096 deja 2,1× de margen sobre la peor página real y corta la desbocada al 10 % de su
coste. Desde el 2026-09-16 el techo es la segunda red y no la primera: el motor deja de leer
la respuesta en cuanto su cola es una repetición (`core/repetition.py`), y una respuesta
que no termina — por bucle o por techo — se pide UNA vez más con el prompt diciendo qué
se repitió. Si tampoco termina, la página se marca como FALLIDA (`FAILED_PAGE_PREFIXES`) y
conserva debajo lo que se leyó antes del bucle: una página cortada en silencio es la
pérdida que este proyecto no acepta, y una marcada sale en rojo en «Apuntes y ejercicios»,
donde se completa a mano. Subir este valor solo tiene sentido para una página de verdad
larguísima; un bucle no lo llena, lo corta el detector antes.

No forma parte de la huella de la caché: subirlo o bajarlo no vuelve a transcribir nada.""",
    ),
    Setting(
        key="builders.transcribe_seam_chars",
        name="TRANSCRIBE_SEAM_CHARS",
        kind="int",
        default=1200,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe_seam",
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
        key="builders.transcribe_page_max_a4_areas",
        name="TRANSCRIBE_PAGE_MAX_A4_AREAS",
        kind="int",
        default=2,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe",
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántas páginas A4 de superficie puede cubrir un render a la resolución configurada. Dos es
un A3 a densidad completa; una página declarada más grande se renderiza a menos resolución
en vez de a un tamaño que ningún endpoint acepta. A4 es la página sobre la que se midió
cada resolución de esta ruta.

Forma parte de la huella de las páginas de un PDF: cambiarlo vuelve a leerlos.""",
    ),
    Setting(
        key="builders.transcribe_page_png_max_bytes",
        name="TRANSCRIBE_PAGE_PNG_MAX_BYTES",
        kind="int",
        default=2 * 1024 * 1024,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe",
        impact=Impact.NONE,
        minimum=0,
        doc="""Una página con texto se envía como PNG sin pérdida salvo que pese más que esto (en bytes),
y entonces va como JPEG. Es una quinta parte de la petición entera de Cerebras y queda muy
por encima de cualquier página compuesta (un A4 de texto a 200 ppp son ~0,6 MB); una página
SIN capa de texto es una foto de papel y va como JPEG desde el principio. Medido el
2026-09-15: los tres boletines escaneados de enfermería fallaban en TODAS sus páginas con el
413 de Cerebras (10 MiB por petición), y la misma página como JPEG se leyó en 0,9 s.

Vale también para las imágenes de un Word o un PowerPoint. Forma parte de la huella de
página: cambiarlo vuelve a leer lo transcrito.""",
    ),
    Setting(
        key="builders.transcribe_page_jpeg_quality",
        name="TRANSCRIBE_PAGE_JPEG_QUALITY",
        kind="int",
        default=90,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe",
        impact=Impact.NONE,
        minimum=1,
        maximum=100,
        doc="""La calidad JPEG de una página escaneada o demasiado pesada para PNG: el escaneo A4 sintético
midió 1,8 MB como PNG y 0,4 MB a 90. Vale también para las imágenes de un Word o un
PowerPoint que pasan a JPEG. Forma parte de la huella de página: cambiarla vuelve a leer lo
transcrito.""",
    ),
    Setting(
        key="builders.transcribe_image_min_long_side",
        name="TRANSCRIBE_IMAGE_MIN_LONG_SIDE",
        kind="int",
        default=1024,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe_image",
        impact=Impact.NONE,
        minimum=0,
        doc="""Una imagen de un Word o un PowerPoint se amplía por un factor entero hasta que su lado mayor
llega a estos píxeles. Medido sobre `gemma-4-31b` con las imágenes legibles de los dos
bancos de referencia (de 188×30 a 1366×768), nativa y ampliada contestaron byte a byte lo
mismo: allí no compra nada y cuesta unos cientos de tokens. Está por el modelo local de
transcripción, que no se ha medido. 0 no amplía nada.

Las lecturas de imágenes se guardan por sus bytes, así que cambiarlo vuelve a leer cada
imagen la próxima vez que se transcriba su documento; forma parte de la huella.""",
    ),
    Setting(
        key="builders.transcribe_image_max_pixels",
        name="TRANSCRIBE_IMAGE_MAX_PIXELS",
        kind="int",
        default=7_750_000,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe_image",
        impact=Impact.NONE,
        minimum=1,
        doc="""Una imagen de un Word o un PowerPoint con más píxeles que esto se reduce antes de la
llamada: es lo que cabe en dos A4 a 200 ppp, lo más que deja llegar un render de página a
la resolución por defecto. Una foto pegada entera en un documento es la gemela de un
escaneo. Forma parte de la huella: cambiarlo vuelve a leer las imágenes.""",
    ),
    Setting(
        key="builders.transcribe_metafile_raster_scale",
        name="TRANSCRIBE_METAFILE_RASTER_SCALE",
        kind="int",
        default=4,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe_image",
        impact=Impact.NONE,
        minimum=1,
        maximum=16,
        doc="""A cuántas veces la página de 96 ppp exporta LibreOffice un dibujo EMF/WMF de un Word o un
PowerPoint. 4× son 384 ppp, que convierten una ecuación de 96×13 px en 380×54: resolución
vectorial y no una ampliación. La ruta por PDF se midió y se descartó: perdía la mitad de
texto del logotipo del cuaderno de referencia, que la exportación a PNG conservaba. El
margen del recorte son 16 px, cuatro puntos de papel a 4×.

Forma parte de la huella: cambiarlo vuelve a leer las imágenes de los documentos de Office.""",
    ),
    Setting(
        key="builders.transcribe_metafile_timeout_seconds",
        name="TRANSCRIBE_METAFILE_TIMEOUT_SECONDS",
        kind="int",
        default=180,
        group="Constructores",
        stages=("transcription",),
        phase="transcribe_image",
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuánto puede tardar LibreOffice en convertir los dibujos EMF/WMF de un documento antes de
darlo por fallido; sin conversión esos dibujos se leen como «[IMAGEN NO LEGIBLE]». Sin
medir: es el techo de un documento con muchos dibujos, no el tiempo de uno.""",
    ),
    Setting(
        key="builders.transcribe_loop_lines",
        name="TRANSCRIBE_LOOP_LINES",
        kind="int",
        default=24,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=2,
        doc="""Cuántas líneas finales tienen que repetirse para declarar un bucle de líneas. Una cuadrícula
dibujada son decenas de filas idénticas; una tabla de verdad no repite nada tan largo, y una
página de código escrita por una persona no lleva veinticuatro líneas idénticas seguidas.
Medido en la instalación de referencia: una página de filas «| | | |» se cortó tres veces en
el techo de 4.096 tokens con los mismos 7.368 caracteres.

El detector también revisa las páginas ya guardadas: cambiarlo puede marcar como bucle, y
volver a leer, páginas que hoy se dan por buenas.""",
    ),
    Setting(
        key="builders.transcribe_loop_max_line_period",
        name="TRANSCRIBE_LOOP_MAX_LINE_PERIOD",
        kind="int",
        default=8,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""El bloque de líneas más largo que cuenta como una unidad repetida. Por encima, la repetición
es contenido: dos estrofas idénticas son dos estrofas. El detector también revisa las
páginas ya guardadas.""",
    ),
    Setting(
        key="builders.transcribe_loop_min_line_repeats",
        name="TRANSCRIBE_LOOP_MIN_LINE_REPEATS",
        kind="int",
        default=4,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=2,
        doc="""Cuántas repeticiones de un bloque hacen falta como mínimo, sea cual sea su longitud, para
declarar un bucle de líneas. El detector también revisa las páginas ya guardadas.""",
    ),
    Setting(
        key="builders.transcribe_loop_chars",
        name="TRANSCRIBE_LOOP_CHARS",
        kind="int",
        default=400,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántos caracteres tienen que repetir una unidad corta para declarar un bucle de caracteres:
una regla de cuatrocientos guiones bajos es un dibujo y no texto, y ni un separador de tabla
Markdown ni el subrayado de un título llegan tan lejos. El detector también revisa las
páginas ya guardadas.""",
    ),
    Setting(
        key="builders.transcribe_loop_max_char_period",
        name="TRANSCRIBE_LOOP_MAX_CHAR_PERIOD",
        kind="int",
        default=16,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""La unidad más larga, en caracteres, que cuenta como repetida en un bucle de caracteres
(`\\_`, una raya, una fila de puntos). Sin medir. El detector también revisa las páginas ya
guardadas.""",
    ),
    Setting(
        key="builders.transcribe_loop_char_run_repeats",
        name="TRANSCRIBE_LOOP_CHAR_RUN_REPEATS",
        kind="int",
        default=24,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=2,
        doc="""Cuántas veces seguidas tiene que repetirse una unidad corta, además de su primera aparición,
en cualquier punto del texto para medirla como posible bucle de caracteres. Es el suelo que impide que la búsqueda se pare en
cada letra doble de la prosa; lo que encuentra se mide después contra
`TRANSCRIBE_LOOP_CHARS`. Sin medir.""",
    ),
    Setting(
        key="builders.transcribe_loop_quote_chars",
        name="TRANSCRIBE_LOOP_QUOTE_CHARS",
        kind="int",
        default=60,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuánto de la unidad repetida se cita: al modelo en el segundo intento y a una persona en la
marca de página fallida. Una fila de cuadrícula son treinta caracteres; el resto de una
unidad larga no dice nada.""",
    ),
    Setting(
        key="builders.transcribe_loop_stream_window_chars",
        name="TRANSCRIBE_LOOP_STREAM_WINDOW_CHARS",
        kind="int",
        default=12_000,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántos caracteres finales de una respuesta en curso mira el motor local para decidir si se
ha quedado en bucle y dejar de leerla. Doce mil caracteres caben la racha más larga que el
detector necesita a cualquier longitud de línea que produce una página. Solo en Ollama:
Cerebras contesta entera y se revisa al final.""",
    ),
    Setting(
        key="builders.transcribe_loop_stream_check_chars",
        name="TRANSCRIBE_LOOP_STREAM_CHECK_CHARS",
        kind="int",
        default=256,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""Cada cuántos caracteres nuevos de una respuesta en curso se vuelve a preguntar si se ha
quedado en bucle. Mirar cada cuarto de kilobyte es lo que mantiene el coste de mirar por
debajo del de un token; más pequeño corta antes y comprueba más veces. Solo en Ollama.""",
    ),
    Setting(
        key="builders.raw_max_file_mb",
        name="RAW_MAX_FILE_MB",
        kind="int",
        default=512,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""El mayor archivo, en MB, que se acepta al subir material en bruto. Un techo contra el disco
y contra una subida equivocada, no una medida de lo que se puede leer.""",
    ),
    Setting(
        key="builders.raw_max_files",
        name="RAW_MAX_FILES",
        kind="int",
        default=100,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántos archivos como máximo caben en un solo envío al material en bruto. Un envío mayor se
rechaza entero antes de escribir nada.""",
    ),
    Setting(
        key="builders.raw_max_request_mb",
        name="RAW_MAX_REQUEST_MB",
        kind="int",
        default=1024,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántos MB puede sumar un solo envío al material en bruto, contando todos sus archivos.""",
    ),
    Setting(
        key="builders.raw_max_slot_gb",
        name="RAW_MAX_SLOT_GB",
        kind="int",
        default=4,
        group="Constructores",
        stages=("transcription",),
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántos GB puede ocupar cada procedencia del material en bruto (los apuntes, los ejercicios)
de una asignatura, contando lo que ya tiene.""",
    ),
    Setting(
        key="builders.exemplars_ocr",
        name="EXEMPLARS_OCR",
        kind="bool",
        default=True,
        group="Constructores",
        stages=("transcription", "profile", "bank"),
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
        stages=("profile",),
        phase="ep_scan",
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
        stages=("profile",),
        phase="ep_scan",
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
        stages=("profile",),
        phase="ep_consolidate",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántas modalidades distintas conserva el constructor del perfil tras el escaneo,
para que un corpus ruidoso no fragmente el perfil en modalidades casi duplicadas.""",
    ),
    Setting(
        key="builders.ep_max_excerpts_per_type",
        name="EP_MAX_EXCERPTS_PER_TYPE",
        kind="int",
        default=3,
        group="Constructores",
        stages=("profile",),
        phase="ep_consolidate",
        impact=Impact.NONE,
        minimum=0,
        doc="""Cuántos fragmentos literales de cada modalidad que el rastreo encontró llegan a la
consolidación del perfil. Son lo que le enseña al modelo cómo es de verdad un ejercicio de
ese tipo, y cada uno pesa lo que `EP_SCAN_EXCERPT_CHARS`. Sin medir.""",
    ),
    Setting(
        key="builders.ep_max_signals_per_type",
        name="EP_MAX_SIGNALS_PER_TYPE",
        kind="int",
        default=3,
        group="Constructores",
        stages=("profile",),
        phase="ep_consolidate",
        impact=Impact.NONE,
        minimum=0,
        doc="""Cuántas de las señales que el rastreo anotó para cada modalidad (lo que la delata en el
material) llegan a la consolidación del perfil. Sin medir.""",
    ),
    Setting(
        key="builders.ep_context_excerpts",
        name="EP_CONTEXT_EXCERPTS",
        kind="int",
        default=3,
        group="Constructores",
        stages=("profile",),
        phase="ep_context",
        impact=Impact.NONE,
        minimum=0,
        doc="""Cuántos ejercicios literales ve la síntesis del contexto de la asignatura. Tres bastan para
fijar la materia, el nivel y la notación, y son pocos para que el tema de un solo ejercicio
no se cuele en el texto.""",
    ),
    Setting(
        key="builders.eb_chunk_size",
        name="EB_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        stages=("bank",),
        phase="eb_extract",
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
        stages=("bank",),
        phase="eb_extract",
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
        key="builders.eb_overlap_max_share",
        name="EB_OVERLAP_MAX_SHARE",
        kind="float",
        default=0.5,
        group="Constructores",
        stages=("bank",),
        phase="eb_extract",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=0.9,
        doc="""Qué fracción de un lote del banco pueden ocupar, como mucho, los bloques que el solape
(`EB_BATCH_OVERLAP_BLOCKS`) arrastra del lote anterior. Arrastrar un bloque que llena medio
presupuesto devolvería el corte siguiente al mismo bloque y podría impedir que los lotes
avancen; por eso el techo queda por debajo de uno. Sin medir.""",
    ),
    Setting(
        key="builders.kg_chunk_size",
        name="KG_BUILDER_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        stages=("graph",),
        phase="kg_extract",
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
        stages=("graph",),
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
        stages=("graph",),
        phase="kg_extract",
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
        stages=("graph",),
        phase="kg_extract",
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
        stages=("graph",),
        phase="kg_extract",
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
        stages=("graph",),
        phase="kg_extract",
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
        stages=("graph", "generation"),
        phase="kg_clean_merge",
        impact=Impact.NONE,
        doc="""Sufijos que se quitan al normalizar la clave de un concepto para compararlo en la fusión,
de modo que las menciones en plural y en singular del mismo concepto se reconozcan como
una sola.""",
    ),
    Setting(
        key="builders.kg_min_singularize_length",
        name="KG_MIN_SINGULARIZE_LENGTH",
        kind="int",
        default=3,
        group="Constructores",
        stages=("graph",),
        phase="kg_clean_merge",
        impact=Impact.NONE,
        minimum=0,
        doc="""La fusión mecánica quita un sufijo de plural (`KG_BUILDER_PLURAL_SUFFIXES`) solo a palabras
más largas que esto, para que «gas» o «mes» no pierdan su última letra. Sin medir.""",
    ),
    Setting(
        key="builders.kg_merge_resplit_ceiling",
        name="KG_MERGE_RESPLIT_CEILING",
        kind="float",
        default=0.95,
        group="Constructores",
        stages=("graph",),
        phase="kg_clean_merge",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=1.0,
        doc="""Los candidatos a fusión se agrupan por parecido y los grupos se encadenan (A~B y B~C juntan
C con A aunque no se parezcan), así que un grupo mayor que `KG_BUILDER_MAX_MERGE_GROUP` se
vuelve a cortar con un umbral más estricto. Por encima de este umbral se deja de cortar y el
grupo se entrega como esté. Sin medir.""",
    ),
    Setting(
        key="builders.kg_merge_resplit_step",
        name="KG_MERGE_RESPLIT_STEP",
        kind="float",
        default=0.05,
        group="Constructores",
        stages=("graph",),
        phase="kg_clean_merge",
        impact=Impact.NONE,
        minimum=0.001,
        maximum=1.0,
        doc="""Cuánto sube el umbral de parecido en cada nuevo corte de un grupo de fusión demasiado
grande. Más pequeño corta más fino y llama más veces al embebedor. Sin medir.""",
    ),
    Setting(
        key="builders.kg_min_leader_runs",
        name="KG_MIN_LEADER_RUNS",
        kind="int",
        default=3,
        group="Constructores",
        stages=("graph",),
        phase="kg_extract",
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántas rachas de puntos guía («.....») hacen falta para tomar un párrafo por un índice y no
anclar ningún concepto en él. Se mira eso y no la densidad de puntuación ni la longitud de
línea, que fallan con prosa de verdad: tres rachas es lo que separa un índice de una frase
con puntos suspensivos.""",
    ),
    Setting(
        key="builders.kg_min_units",
        name="KG_MIN_UNITS",
        kind="int",
        default=2,
        group="Constructores",
        stages=("graph",),
        phase="kg_units",
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántas unidades del temario tienen que sobrevivir a la verificación para aceptar la
segmentación; por debajo, la fase entera cae al camino que nombra los dominios sin mirar la
estructura del material. Una unidad no es un temario. El prompt pide entre 3 y 12: este es
el suelo de lo que se acepta, no lo que se pide.""",
    ),
    Setting(
        key="builders.kg_taggable_samples_per_domain",
        name="KG_TAGGABLE_SAMPLES_PER_DOMAIN",
        kind="int",
        default=3,
        group="Constructores",
        stages=("graph",),
        phase="kg_taggable",
        impact=Impact.NONE,
        minimum=0,
        doc="""Cuántos enunciados reales del banco que tocan un dominio ve la revisión de etiquetabilidad
de ese dominio. Son lo que le deja juzgar si un concepto discrimina entre ejercicios de
verdad. Sin medir.""",
    ),
    Setting(
        key="builders.kg_taggable_sample_chars",
        name="KG_TAGGABLE_SAMPLE_CHARS",
        kind="int",
        default=300,
        group="Constructores",
        stages=("graph",),
        phase="kg_taggable",
        impact=Impact.NONE,
        minimum=1,
        doc="""Cuántos caracteres de cada enunciado de muestra llegan a la revisión de etiquetabilidad.
Sin medir.""",
    ),
    Setting(
        key="builders.kg_min_mention_length",
        name="KG_MIN_MENTION_LENGTH",
        kind="int",
        default=3,
        group="Constructores",
        stages=("graph", "generation"),
        phase="kg_extract",
        impact=Impact.NONE,
        minimum=1,
        doc="""La palabra más corta del nombre de un concepto que cuenta al buscar si un texto lo menciona
(`core/lexicon.py`). La usan el anclaje de los conceptos a sus pasajes del material y la
comprobación de que un ejercicio generado no mencione un concepto aún no impartido. Sin
medir.""",
    ),
    Setting(
        key="builders.kg_mention_inflection_slack",
        name="KG_MENTION_INFLECTION_SLACK",
        kind="int",
        default=2,
        group="Constructores",
        stages=("graph", "generation"),
        phase="kg_extract",
        impact=Impact.NONE,
        minimum=0,
        doc="""Cuántos caracteres puede añadir la flexión a una palabra del nombre de un concepto para que
un texto cuente como que lo menciona: «bucle» casa con «bucles». La usan el anclaje de los
conceptos y la comprobación de conceptos aún no impartidos. Sin medir.""",
    ),
    Setting(
        key="builders.kg_merge_qualifier_pattern",
        name="KG_BUILDER_MERGE_QUALIFIER_PATTERN",
        kind="str",
        default=r"\s+en (python|java)\b",
        group="Constructores",
        stages=("graph",),
        phase="kg_clean_merge",
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
        stages=("graph",),
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
        stages=("graph",),
        phase="kg_extract",
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
        stages=("graph",),
        phase="kg_extract",
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
        stages=("graph",),
        phase="kg_clean_merge",
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
        stages=("graph",),
        phase="kg_clean_merge",
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
        stages=("graph",),
        phase="kg_clean_merge",
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
        stages=("graph",),
        phase="kg_clean_drop",
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
        stages=("graph",),
        phase="kg_domains_leftovers",
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
        stages=("graph",),
        phase="kg_domains_leftovers",
        impact=Impact.NONE,
        minimum=1,
        doc="""Acota cuántas veces `place_leftovers` vuelve a pedir al modelo que coloque los conceptos
que dejó sin clasificar, antes de que lo que quede vaya a `KG_BUILDER_UNCLASSIFIED_DOMAIN`.""",
    ),
]
