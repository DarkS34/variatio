"""The Spanish wording, the default and the one every measurement was taken on.

Interchangeable with `en` by construction: the same names with the same shapes, which is
what lets a component hold one without knowing which. Every string here was a literal
somewhere under `variatio/` before this module existed, and is preserved verbatim.
"""

from . import shared

LANGUAGE = "es"

# PROMPT INJECTION -------------------------------------------------------------------------------

OVERRIDE_VERBS: str = (
    r"olvida(?:te|d)?|olvides|ignora(?:d)?|ignores|omite|omitas|omitid|"
    r"descarta(?:d)?|descartes|obvia|obvies|anula(?:d)?|anules|salta(?:te)?|saltes|"
    r"incumple|desobedece|haz caso omiso|"
    r"no (?:sigas|obedezcas|cumplas|respetes|apliques|tengas en cuenta)|"
    r"deja de (?:seguir|obedecer|aplicar|hacer caso)|"
) + shared.OVERRIDE_VERBS

OVERRIDE_OBJECTS: str = (
    r"instruccion(?:es)?|indicacion(?:es)?|regla(?:s)?|orden(?:es)?|consigna(?:s)?|"
    r"restriccion(?:es)?|directriz|directrices|"
) + shared.OVERRIDE_OBJECTS

OVERRIDE_QUALIFIERS: str = r"anterior(?:es)?|previ[ao]s?|de arriba|" + shared.OVERRIDE_QUALIFIERS

# The lookahead spares "instrucciones del sistema operativo", a legitimate subject.
INJECTION_PATTERNS: tuple[str, ...] = shared.INJECTION_PATTERNS + (
    r"\bprompt del sistema\b",
    r"\binstrucciones del sistema\b(?! ?operativ)",
)

# WORD MATCHING ----------------------------------------------------------------------------------

STOPWORDS: frozenset[str] = frozenset(
    {"de", "del", "la", "el", "los", "las", "en", "y", "o", "a", "un", "una", "por", "con", "para"}
)

# THE GUARDRAIL'S VERDICT ------------------------------------------------------------------------

GUARDRAIL_LABELS: dict[str, str] = {
    "instruction_override": "una instrucción dirigida al sistema, no al ejercicio",
    "harm": "contenido dañino",
    "jailbreak": "un intento de saltarse las instrucciones del sistema",
    "social_bias": "sesgo contra un colectivo",
    "violence": "violencia",
    "profanity": "lenguaje ofensivo",
    "sexual_content": "contenido sexual",
    "unethical_behavior": "comportamiento poco ético",
}


def guardrail_blocked(reason: str) -> str:
    """Say why the free text did not pass the safety screen."""
    return f"Las instrucciones adicionales no han pasado la revisión: se ha detectado {reason}."


# THE FREE-TEXT CATALOGUE ------------------------------------------------------------------------

SLOTS: tuple[tuple[str, str, str], ...] = (
    ("ambito", "Ámbito", "que vaya de una panadería"),
    ("elementos", "Elementos del enunciado", "con una tabla de datos"),
    ("extension", "Extensión", "un enunciado breve"),
    ("datos", "Datos concretos", "que la lista tenga al menos 10 elementos"),
)

OWNER_CONCEPTS: tuple[str, str] = ("los conceptos objetivo", "elígelos en el paso de conceptos")
OWNER_DIFFICULTY_WHERE: str = "elígelo en «¿De qué nivel?»"
OWNER_FIELD_WHERE: str = "decídelo en «¿Cómo debe ser?»"
OWNER_ITEM_TYPE: tuple[str, str] = ("la modalidad del ejercicio", "elígela en el paso de modalidad")
OWNER_CONTEXT: tuple[str, str] = (
    "la materia, el nivel y el idioma",
    "los fija el contexto de la asignatura, en el panel",
)


def scope_blocked(text: str, owner: str, term: str, where: str) -> str:
    """Say which control already decides what the free text is asking for."""
    # "lo decide" agreed with nothing: two of the four owners are plural ("los conceptos
    # objetivo", "la materia, el nivel y el idioma"), so the sentence read "lo decide los
    # conceptos objetivo". "corresponde a" agrees with all four.
    return f"«{text}» no se pide aquí: eso corresponde a {owner} («{term}»). {where}."


# WHAT THE CHECKS REPORT -------------------------------------------------------------------------

def check_empty_primary(field: str) -> str:
    """The primary field carries nothing worth keeping."""
    return f"el campo principal «{field}» está vacío o es demasiado corto"


def check_missing_fields(names: list[str]) -> str:
    """Required fields came back empty."""
    return f"campo(s) obligatorio(s) sin contenido: {', '.join(names)}"


def check_mentions_untaught(concepts: list[str]) -> str:
    """The item names something the curriculum says has not been taught."""
    return f"menciona lo no impartido: {', '.join(concepts)}"


def check_practises_later(concepts: list[str]) -> str:
    """The item practises a concept that comes after the target."""
    return f"practica lo que va después del objetivo: {', '.join(concepts)}"


def check_too_similar(label: str, score: float) -> str:
    """The item is too close to an exemplar or to another of its own batch."""
    return f"muy parecida a {label} ({score:.2f})"


def check_tagger_missed(targets: list[str], seen: str | None) -> str:
    """The tagger did not find any target among the item's tags."""
    missed = f"el etiquetador no la reconoce como {' / '.join(targets)}"
    return f"{missed}; la etiqueta como «{seen}»" if seen else missed


def batch_label(position: int) -> str:
    """Name one item of the batch in flight, for the similarity report."""
    return f"lote {position}"


# WHAT A TRANSCRIPTION LEAVES ON A PAGE ------------------------------------------------------------

FAILED_PAGE_PREFIX: str = "> [TRANSCRIPCIÓN FALLIDA"
UNREADABLE_IMAGE_MARK: str = "[IMAGEN NO LEGIBLE]"


def failed_page(index: int, count: int, error: str) -> str:
    """Mark a page the model could not read, naming what went wrong."""
    return f"{FAILED_PAGE_PREFIX} — página {index} de {count}: {error}]"


def failed_page_truncated(index: int, count: int, cap: int, setting: str) -> str:
    """Mark a page whose answer hit the output cap instead of ending."""
    return (
        f"{FAILED_PAGE_PREFIX} — página {index} de {count}: la respuesta superó el techo "
        f"de {cap} tokens de salida; el modelo se quedó repitiendo algo de la página "
        "(una línea de puntos, un borde) en vez de terminar. Corrígela a mano o sube "
        f"{setting} en «Configuración» si de verdad era una página tan larga]"
    )


# FRAGMENTS THE PROMPT BLOCKS ARE ASSEMBLED FROM ----------------------------------------------------

UNNAMED_CONCEPT: str = "concepto previo"
NO_DESCRIPTION: str = "sin descripción"
OPTIONAL_FIELD: str = "opcional"
TYPE_LIST: str = "lista"
TYPE_OBJECT: str = "objeto"
TYPE_VALUE: str = "valor"
TYPE_OR: str = " o "


def neighbour_note(concept: str) -> str:
    """Warn that a few-shot exemplar illustrates a neighbouring concept, not the target."""
    return f"(Ejemplo de un concepto previo: «{concept}». Referencia de forma, no del objetivo.)"


def relations_sentence(clauses: list[str]) -> str:
    """Describe an undescribed concept by what the graph says it is related to."""
    return "Sin descripción; en el grafo " + "; ".join(clauses) + "."


def other_modalities(names: list[str]) -> str:
    """Name the sibling modalities the generator must stay away from."""
    return "Otras modalidades de la asignatura, que NO debes producir aquí: " + ", ".join(names) + "."


def hand_written_guidance(text: str) -> str:
    """Introduce the guidance somebody wrote by hand for one field."""
    return f"Guía anotada a mano para este campo: {text}"


def schema_description(text: str) -> str:
    """Introduce a field's own description from the schema."""
    return f"Descripción del schema: {text}"


def fixed_value(name: str, value: str) -> str:
    """State that a field is pinned to one exact value."""
    return f"- `{name}`: debe ser exactamente {value}."


def type_list_of(inner: str) -> str:
    """Name a list field by what it holds."""
    return f"lista de {inner}"


ITEM_SCHEMA_HEADING: str = "Schema de un ítem de esta modalidad:"
EXTRACTION_GUIDE_HEADING: str = "Guía de extracción por campo — síguela literalmente:"


def modalities_heading(count: int) -> str:
    """Open the list of modalities the subject sets its tasks in."""
    return f"La asignatura plantea sus tareas en {count} modalidad(es):"


def seen_in_chunks(count: int) -> str:
    """Say how much evidence the scan found for one modality."""
    return f"Visto en {count} fragmento(s)."


def signals_line(signals: list[str]) -> str:
    """List the signals the scan matched a modality by."""
    return "Señales: " + " | ".join(signals)


def fields_line(fields: list[str]) -> str:
    """List the fields the scan observed on a modality."""
    return "Campos observados: " + ", ".join(fields)


def exemplar_heading(location: str) -> str:
    """Introduce one verbatim excerpt, naming where it came from."""
    return f"Ejemplar ({location}):"


PASSAGE_CONCEPTS_HEADING: str = "CONCEPTOS EXTRAÍDOS DE AQUÍ: "
DESCRIBING_MARK: str = " (el que estás describiendo)"
CONTEXT_SOURCE_PROFILE: str = "EL PERFIL DE EJEMPLARES"
CONTEXT_SOURCE_GRAPH: str = "EL GRAFO DEL TEMARIO"


def syllabus_blocks(domains: int, concepts: int) -> str:
    """Open the graph's evidence for the subject-context synthesis."""
    return (
        f"El temario se divide en {domains} bloque(s), con {concepts} concepto(s) "
        "en total. Se llaman:"
    )
