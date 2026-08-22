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
        doc="""Page-image transcription of raw exemplars. Docling reads these PDFs as text and loses
three things at once: it detaches code blocks from the question that cites them, it
collapses their line breaks, and it drops the colour that marks the correct option.
Rendering the page and reading it as an image recovers all three.""",
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
        doc="""Transcription is copying, not writing: at Ollama's default temperature the same page
came back with `a = 99` and `if a < 0 : break` dedented out of their `while True:`,
which silently changes what the exercise asks. Pinned to 0 for that reason.

It stays a constant of its own rather than becoming `TEMPERATURE_DETERMINISTIC`, although
it holds the same number and for the same reason: this one is part of the page cache's
fingerprint (`_source_docs/pages.py`), so changing it re-transcribes every page of every
corpus. Aliasing it would make that consequence follow from an edit made about something
else entirely.""",
    ),
    Setting(
        key="builders.transcribe_max_retries",
        name="TRANSCRIBE_MAX_RETRIES",
        kind="int",
        default=1,
        group="Constructores",
        impact=Impact.NONE,
        minimum=0,
        doc="""Number of times the page-image transcription is retried after a parse failure before
the builder gives up on that page and falls back to Docling's own text extraction.""",
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
        doc="""Bump when transcribe_page_prompt changes: it is part of the page cache fingerprint.

Lo sube quien edita el prompt, no quien mira una pantalla.""",
    ),
    Setting(
        key="builders.exemplars_ocr",
        name="EXEMPLARS_OCR",
        kind="bool",
        default=True,
        group="Constructores",
        impact=Impact.NONE,
        doc="""Only reached by the Docling fallback (non-PDF sources, or PDFs whose transcription
failed): scanned pages whose text never made it into the PDF at all.""",
    ),
    Setting(
        key="builders.ep_chunk_size",
        name="EP_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps the number of characters per chunk when the exemplars-profile builder splits a
source document for scanning, keeping each call within the model's usable context.""",
    ),
    Setting(
        key="builders.ep_scan_excerpt_chars",
        name="EP_SCAN_EXCERPT_CHARS",
        kind="int",
        default=400,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Bounds how many characters of each scanned item type's excerpt are kept, enough to
recognise the modality without carrying the whole example into every later call.""",
    ),
    Setting(
        key="builders.ep_max_item_types",
        name="EP_MAX_ITEM_TYPES",
        kind="int",
        default=6,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps how many distinct item types the exemplars-profile builder will keep from a
scan, so a noisy corpus cannot fragment the profile into near-duplicate modalities.""",
    ),
    Setting(
        key="builders.eb_chunk_size",
        name="EB_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps the number of characters per chunk when the exemplars-bank builder batches a
source document's markdown for extraction.""",
    ),
    Setting(
        key="builders.kg_chunk_size",
        name="KG_BUILDER_CHUNK_SIZE",
        kind="int",
        default=12000,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps the number of characters per chunk the knowledge-graph builder reads at a time
during extraction, bounding how much text one extraction call has to reason over.""",
    ),
    Setting(
        key="builders.kg_max_evidence_relations",
        name="KG_MAX_EVIDENCE_RELATIONS",
        kind="int",
        default=6,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps how many relation triples are shown as evidence for a concept in the cleaning
and domain-assignment prompts, so a hub concept cannot crowd out the rest of the batch.""",
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
        doc="""Suffixes stripped when normalising a concept's key for merge comparison, so plural
and singular mentions of the same concept are recognised as one.""",
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
        doc="""Caps how many section titles per source document are offered as domain-naming
evidence, so one document with many headings cannot dominate the domain-naming call.""",
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
        doc="""The fraction of documents a heading must appear in before it counts as a recurring
section title rather than a one-off, feeding the domain-naming call.""",
    ),
    Setting(
        key="builders.kg_relation_schema",
        name="KG_RELATION_SCHEMA",
        kind="str",
        default="es",
        group="Constructores",
        impact=Impact.LOCKED,
        editable=False,
        doc="""Selects which relation vocabulary from `relations.py` the graph uses; it fixes the
Spanish verbose labels the loader indexes the graph by.

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
        doc="""The cosine-similarity floor above which two concept names are proposed to the
merge-decision call as candidates for being the same concept, during graph cleaning.""",
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
        doc="""Caps how many candidate merge groups are bundled into a single cleaning call,
bounding how much the model must decide on at once.""",
    ),
    Setting(
        key="builders.kg_clean_batch_size",
        name="KG_BUILDER_CLEAN_BATCH_SIZE",
        kind="int",
        default=60,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps how many concepts are sent to the model in one batch during the cleaning
phase's merge and drop passes.""",
    ),
    Setting(
        key="builders.kg_domain_batch_size",
        name="KG_BUILDER_DOMAIN_BATCH_SIZE",
        kind="int",
        default=20,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps how many concepts are placed into domains in a single `assign_round` call,
keeping the per-call placement batch small enough to judge accurately.""",
    ),
    Setting(
        key="builders.kg_domain_rounds",
        name="KG_BUILDER_DOMAIN_ROUNDS",
        kind="int",
        default=3,
        group="Constructores",
        impact=Impact.NONE,
        minimum=1,
        doc="""Caps how many times `place_leftovers` re-asks the model to place concepts it left
unclassified, before whatever remains is given up to `KG_BUILDER_UNCLASSIFIED_DOMAIN`.""",
    ),
]
