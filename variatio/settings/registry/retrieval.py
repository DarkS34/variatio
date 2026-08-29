"""The «Recuperación» settings: the embedder's prefixes, its band and how it describes."""

from ..types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(key="retrieval.query_prefix", name="EMBEDDING_QUERY_PREFIX", kind="str",
            default="Instruct: Dado el enunciado de un ejercicio, recupera la descripción del concepto del currículo que el ejercicio hace practicar al alumno, no la de los que solo usa como herramienta\nQuery: ",
            group="Recuperación", impact=Impact.REINDEX, doc="""Sigue diciendo «el enunciado de un ejercicio» aunque `embed_fields` pueda añadir ahora el
código que el ítem le entrega al alumno. Generalizarlo a «un ejercicio» se probó y SE MIDIÓ
PEOR, así que la redacción se queda: sobre el banco de referencia movió 17 de 152 top-1 y
costó margen (0.0345 → 0.0328), bajando el top-1 más bajo de 0.4065 a 0.3902 — por debajo
del umbral de más abajo, es decir, un ítem que recibía candidatos deja de recibir ninguno.
Sobre el banco de pruebas multicampo, donde debería haber salido a cuenta, quedó en tablas
(top-1 0.6153 → 0.6045, margen +0.0014). La misma lección que con embeddinggemma: un
prefijo es una afirmación medida, nunca una intuición."""),
    Setting(key="retrieval.document_prefix", name="EMBEDDING_DOCUMENT_PREFIX", kind="str",
            default="", group="Recuperación", impact=Impact.REINDEX,
            doc="""Vacío a propósito: el uso prescrito de qwen3-embedding lleva prefijo en la consulta pero
no en el documento. Un prefijo es una afirmación medida por modelo, nunca una intuición —
véase EMBEDDING_QUERY_PREFIX."""),
    Setting(key="retrieval.batch_size", name="EMBEDDING_BATCH_SIZE", kind="int", default=16,
            group="Recuperación", impact=Impact.NONE, minimum=1,
            doc="""Cuántos textos se envían al modelo de embeddings por llamada a /api/embed; agrupar
amortiza el coste de cada petición a lo largo del banco y del índice de conceptos."""),
    Setting(key="retrieval.field_max_chars", name="EMBEDDING_FIELD_MAX_CHARS", kind="int",
            default=2000, group="Recuperación", impact=Impact.REINDEX, minimum=1,
            doc="""Acota cada campo que `embed_fields` añade DESPUÉS del principal, para que un listado de
código largo no expulse a los demás del contexto. Los perfiles de un solo campo no se
acotan: su texto queda byte a byte idéntico al campo principal, que es lo que mantiene
válidos sus vectores en caché y el umbral de abajo."""),
    Setting(key="retrieval.max_chars", name="EMBEDDING_MAX_CHARS", kind="int", default=12000,
            group="Recuperación", impact=Impact.NONE, minimum=1,
            doc="""El presupuesto seguro de una llamada de embedding, aplicado como AVISO al inicializar y
no truncando. Medido en qwen3-embedding:4b con num_ctx 4096, y los dos caminos no
coinciden: `embed_batch` (/api/embed) trunca en silencio por encima de ~20 000
caracteres, mientras que `embed` (/api/embeddings) devuelve un 500 a ~15 500 — así que
el mismo ítem sobredimensionado se indexa bien y luego revienta al etiquetar. 12 000 deja
margen por debajo del menor de los dos."""),
    Setting(key="retrieval.similarity_threshold", name="EMBEDDER_SIMILARITY_THRESHOLD",
            kind="float", default=0.40, group="Recuperación", impact=Impact.CONTEXTS,
            minimum=0.0, maximum=1.0,
            doc="""Vuelto a medir tras `embed_fields` y SE QUEDA en 0.40: el cambio no mueve la distribución
que acota. En frío (un banco nuevo, puntuado contra descripciones de concepto puras, que
es el régimen en el que corre el etiquetado) la mediana del ruido bajó ligeramente,
0.3418 → 0.3329, y el top-1 real más bajo apenas se movió, 0.5005 → 0.4938. En caliente
(el banco de referencia, puntuado contra el índice fusionado más la pata kNN, que es lo
que el pipeline hace de verdad) la mediana del ruido es 0.3776 — el 0.382 que se anotó
aquí — y el top-1 más bajo es 0.6226. Así que 0.40 sigue por encima del ruido en ambos
regímenes y por debajo de todo top-1 real observado."""),
    Setting(key="retrieval.description_weight", name="EMBEDDER_DESCRIPTION_WEIGHT",
            kind="float", default=0.5, group="Recuperación", impact=Impact.REINDEX,
            minimum=0.0, maximum=1.0,
            doc="""El índice fusionado es α·descripción + (1-α)·centroide(ejemplares); la ponderación existe
porque una media simple dejaba que la descripción se diluyera a 1/(1+n) conforme se
acumulaban ejemplares, de modo que el ancla de un concepto se debilitaba con su
popularidad."""),
    Setting(key="retrieval.description_siblings_top_k", name="DESCRIPTION_SIBLINGS_TOP_K",
            kind="int", default=8, group="Recuperación", impact=Impact.NONE, minimum=1,
            doc="""Cuántos conceptos vecinos por embedding se muestran al prompt de descripción como
contexto de hermanos al escribir o revisar la descripción de un concepto."""),
    Setting(key="retrieval.description_collision_similarity",
            name="DESCRIPTION_COLLISION_SIMILARITY", kind="float", default=0.85,
            group="Recuperación", impact=Impact.NONE, minimum=0.0, maximum=1.0,
            doc="""Similitud coseno por encima de la cual dos descripciones de concepto se marcan como
probable colisión: redactadas tan parecido que no distinguen los conceptos que anclan."""),
    Setting(key="retrieval.description_prompt_version", name="DESCRIPTION_PROMPT_VERSION",
            kind="int", default=2, group="Recuperación", impact=Impact.LOCKED,
            editable=False, minimum=1,
            doc="""Súbelo al cambiar `concept_description_prompt`, igual que `TRANSCRIBE_PROMPT_VERSION` con
la transcripción de páginas. La huella de una descripción mira el grafo y el anclaje al
corpus, que es lo que el prompt interpola — pero no el prompt, así que cambiar las reglas
de redacción dejaba en caché descripciones escritas con las anteriores y no había forma
de notarlo: el texto seguía ahí y el concepto seguía existiendo. La 2 es la que prohíbe
la voz del alumno y exige la salida bajo gramática.

Lo sube quien edita el prompt, no quien mira una pantalla."""),
]
