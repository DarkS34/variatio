from ..types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(key="retrieval.query_prefix", name="EMBEDDING_QUERY_PREFIX", kind="str",
            default="Instruct: Dado el enunciado de un ejercicio, recupera la descripción del concepto del currículo que el ejercicio hace practicar al alumno, no la de los que solo usa como herramienta\nQuery: ",
            group="Recuperación", impact=Impact.REINDEX, doc="""It still says «el enunciado de un ejercicio» although `embed_fields` may now append the
code the item hands the student. Generalising it to «un ejercicio» was tried and MEASURED
WORSE, so the wording stays: on the reference bank it moved 17/152 top-1s and cost margin
(0.0345 → 0.0328), dropping the lowest top-1 from 0.4065 to 0.3902 — under the threshold
below, i.e. one item that got candidates stops getting any. On the multi-field test bank,
where it should have paid off, it was a wash (top-1 0.6153 → 0.6045, margin +0.0014).
Same lesson as embeddinggemma: a prefix is a measured claim, never an intuition."""),
    Setting(key="retrieval.document_prefix", name="EMBEDDING_DOCUMENT_PREFIX", kind="str",
            default="", group="Recuperación", impact=Impact.REINDEX,
            doc="""Empty on purpose: qwen3-embedding's prescribed usage takes a query prefix but no
document prefix. A prefix is a per-model measured claim, never an intuition — see
EMBEDDING_QUERY_PREFIX."""),
    Setting(key="retrieval.batch_size", name="EMBEDDING_BATCH_SIZE", kind="int", default=16,
            group="Recuperación", impact=Impact.NONE, minimum=1,
            doc="""Number of texts sent to the embedding model per call to /api/embed; batching
amortises request overhead across the bank and the concepts index."""),
    Setting(key="retrieval.field_max_chars", name="EMBEDDING_FIELD_MAX_CHARS", kind="int",
            default=2000, group="Recuperación", impact=Impact.REINDEX, minimum=1,
            doc="""Caps each field `embed_fields` appends AFTER the primary one, so one long code listing
cannot crowd the others out of the context. Single-field profiles are not capped: their
text stays byte-identical to the primary field, which is what keeps their cached vectors
and the threshold below valid."""),
    Setting(key="retrieval.max_chars", name="EMBEDDING_MAX_CHARS", kind="int", default=12000,
            group="Recuperación", impact=Impact.NONE, minimum=1,
            doc="""The safe budget for one embedding call, enforced as a WARNING at initialize rather than
by truncating. Measured on qwen3-embedding:4b at num_ctx 4096, and the two paths disagree:
`embed_batch` (/api/embed) silently truncates above ~20 000 chars, while `embed`
(/api/embeddings) raises a 500 at ~15 500 — so the same oversized item indexes fine and
then blows up at tagging time. 12 000 keeps a margin under the lower of the two."""),
    Setting(key="retrieval.similarity_threshold", name="EMBEDDER_SIMILARITY_THRESHOLD",
            kind="float", default=0.40, group="Recuperación", impact=Impact.CONTEXTS,
            minimum=0.0, maximum=1.0,
            doc="""Re-measured after `embed_fields` and it STAYS at 0.40 — the change does not move the
distribution it gates. Cold (a fresh bank, scored against pure concept descriptions, which
is the regime tagging runs in) the noise median went slightly DOWN, 0.3418 → 0.3329, and
the lowest real top-1 barely moved, 0.5005 → 0.4938. Warm (the reference bank, scored
against the merged index + the kNN leg, which is what the pipeline really does) the noise
median is 0.3776 — that is the 0.382 recorded here — and the lowest top-1 is 0.6226.
So 0.40 still sits above the noise in both regimes and below every observed real top-1."""),
    Setting(key="retrieval.description_weight", name="EMBEDDER_DESCRIPTION_WEIGHT",
            kind="float", default=0.5, group="Recuperación", impact=Impact.REINDEX,
            minimum=0.0, maximum=1.0,
            doc="""The merged index is α·description + (1-α)·centroid(exemplars); the weighting exists
because a plain mean let the description fade to 1/(1+n) as exemplars accumulated, so a
concept's anchor weakened with its popularity."""),
    Setting(key="retrieval.description_siblings_top_k", name="DESCRIPTION_SIBLINGS_TOP_K",
            kind="int", default=8, group="Recuperación", impact=Impact.NONE, minimum=1,
            doc="""How many nearest concepts by embedding are shown to the description prompt as sibling
context when writing or reviewing one concept's description."""),
    Setting(key="retrieval.description_collision_similarity",
            name="DESCRIPTION_COLLISION_SIMILARITY", kind="float", default=0.85,
            group="Recuperación", impact=Impact.NONE, minimum=0.0, maximum=1.0,
            doc="""Cosine similarity above which two concept descriptions are flagged as a likely
collision — worded too alike to distinguish the concepts they anchor."""),
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
