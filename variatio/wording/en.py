"""The English wording.

Interchangeable with `es` by construction: the same names with the same shapes. Unmeasured
like the rest of `prompts/en/` — none of the numbers this project quotes about the guardrail
or the scope judge was taken on it.
"""

from . import shared

LANGUAGE = "en"

# PROMPT INJECTION -------------------------------------------------------------------------------

OVERRIDE_VERBS: str = (
    r"skip|omit|drop|discard|breach|disobey|pay no attention to|"
    r"do not (?:obey|apply|respect|comply with|take into account)|"
    r"stop (?:obeying|applying|complying)|"
) + shared.OVERRIDE_VERBS

OVERRIDE_OBJECTS: str = r"order(?:s)?|command(?:s)?|restriction(?:s)?|" + shared.OVERRIDE_OBJECTS

OVERRIDE_QUALIFIERS: str = shared.OVERRIDE_QUALIFIERS

# The lookahead spares "system requirements", a legitimate subject, as the Spanish set
# spares "instrucciones del sistema operativo".
INJECTION_PATTERNS: tuple[str, ...] = shared.INJECTION_PATTERNS + (
    r"\bsystem instructions\b",
    r"\bsystem prompt\b(?! ?requirement)",
)

# WORD MATCHING ----------------------------------------------------------------------------------

STOPWORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "of", "in", "on", "and", "or", "to", "for", "with", "by", "from", "at"}
)

# THE GUARDRAIL'S VERDICT ------------------------------------------------------------------------

GUARDRAIL_LABELS: dict[str, str] = {
    "instruction_override": "an instruction aimed at the system, not at the exercise",
    "harm": "harmful content",
    "jailbreak": "an attempt to get around the system's instructions",
    "social_bias": "bias against a group of people",
    "violence": "violence",
    "profanity": "offensive language",
    "sexual_content": "sexual content",
    "unethical_behavior": "unethical behaviour",
}


def guardrail_blocked(reason: str) -> str:
    """Say why the free text did not pass the safety screen."""
    return f"The additional instructions did not pass the screen: {reason} was detected."


# THE FREE-TEXT CATALOGUE ------------------------------------------------------------------------

SLOTS: tuple[tuple[str, str, str], ...] = (
    ("ambito", "Setting", "set it in a bakery"),
    ("elementos", "Parts of the statement", "with a table of data"),
    ("extension", "Length", "a short statement"),
    ("datos", "Specific data", "the list should have at least 10 elements"),
)

OWNER_CONCEPTS: tuple[str, str] = ("the target concepts", "pick them in the concepts step")
OWNER_DIFFICULTY_WHERE: str = "choose it under «How hard?»"
OWNER_FIELD_WHERE: str = "decide it under «What should it be like?»"
OWNER_ITEM_TYPE: tuple[str, str] = ("the exercise type", "pick it in the type step")
OWNER_CONTEXT: tuple[str, str] = (
    "the subject, the level and the language",
    "the subject's context sets them, in the panel",
)


def scope_blocked(text: str, owner: str, term: str, where: str) -> str:
    """Say which control already decides what the free text is asking for."""
    return f"«{text}» is not asked for here: that is up to {owner} («{term}»). {where}."


# WHAT THE CHECKS REPORT -------------------------------------------------------------------------

def check_empty_primary(field: str) -> str:
    """The primary field carries nothing worth keeping."""
    return f"the primary field «{field}» is empty or too short"


def check_missing_fields(names: list[str]) -> str:
    """Required fields came back empty."""
    return f"required field(s) with no content: {', '.join(names)}"


def check_mentions_untaught(concepts: list[str]) -> str:
    """The item names something the curriculum says has not been taught."""
    return f"mentions what has not been taught: {', '.join(concepts)}"


def check_practises_later(concepts: list[str]) -> str:
    """The item practises a concept that comes after the target."""
    return f"practises what comes after the target: {', '.join(concepts)}"


def check_too_similar(label: str, score: float) -> str:
    """The item is too close to an exemplar or to another of its own batch."""
    return f"very close to {label} ({score:.2f})"


def check_tagger_missed(targets: list[str], seen: str | None) -> str:
    """The tagger did not find any target among the item's tags."""
    missed = f"the tagger does not read it as {' / '.join(targets)}"
    return f"{missed}; it tags it «{seen}»" if seen else missed


def batch_label(position: int) -> str:
    """Name one item of the batch in flight, for the similarity report."""
    return f"batch {position}"


# WHAT A TRANSCRIPTION LEAVES ON A PAGE ------------------------------------------------------------

FAILED_PAGE_PREFIX: str = "> [TRANSCRIPTION FAILED"
UNREADABLE_IMAGE_MARK: str = "[UNREADABLE IMAGE]"


def failed_page(index: int, count: int, error: str) -> str:
    """Mark a page the model could not read, naming what went wrong."""
    return f"{FAILED_PAGE_PREFIX} — page {index} of {count}: {error}]"


def failed_page_truncated(index: int, count: int, cap: int, setting: str) -> str:
    """Mark a page whose answer hit the output cap instead of ending."""
    return (
        f"{FAILED_PAGE_PREFIX} — page {index} of {count}: the answer went over the cap of "
        f"{cap} output tokens; the model kept repeating something from the page (a run of "
        "dots, a border) instead of finishing. Correct it by hand, or raise "
        f"{setting} under «Configuración» if the page really was that long]"
    )


# FRAGMENTS THE PROMPT BLOCKS ARE ASSEMBLED FROM ----------------------------------------------------

UNNAMED_CONCEPT: str = "an earlier concept"
NO_DESCRIPTION: str = "no description"
OPTIONAL_FIELD: str = "optional"
TYPE_LIST: str = "list"
TYPE_OBJECT: str = "object"
TYPE_VALUE: str = "value"
TYPE_OR: str = " or "


def neighbour_note(concept: str) -> str:
    """Warn that a few-shot exemplar illustrates a neighbouring concept, not the target."""
    return f"(Example of an earlier concept: «{concept}». A reference for shape, not for the objective.)"


def relations_sentence(clauses: list[str]) -> str:
    """Describe an undescribed concept by what the graph says it is related to."""
    return "No description; in the graph it " + "; ".join(clauses) + "."


def other_modalities(names: list[str]) -> str:
    """Name the sibling modalities the generator must stay away from."""
    return "Other exercise types of this subject, which you must NOT produce here: " + ", ".join(names) + "."


def hand_written_guidance(text: str) -> str:
    """Introduce the guidance somebody wrote by hand for one field."""
    return f"Guidance written by hand for this field: {text}"


def schema_description(text: str) -> str:
    """Introduce a field's own description from the schema."""
    return f"Schema description: {text}"


def fixed_value(name: str, value: str) -> str:
    """State that a field is pinned to one exact value."""
    return f"- `{name}`: must be exactly {value}."


def type_list_of(inner: str) -> str:
    """Name a list field by what it holds."""
    return f"list of {inner}"


ITEM_SCHEMA_HEADING: str = "Schema of one item of this type:"
EXTRACTION_GUIDE_HEADING: str = "Per-field extraction guidance — follow it literally:"


def modalities_heading(count: int) -> str:
    """Open the list of modalities the subject sets its tasks in."""
    return f"The subject sets its tasks in {count} exercise type(s):"


def seen_in_chunks(count: int) -> str:
    """Say how much evidence the scan found for one modality."""
    return f"Seen in {count} chunk(s)."


def signals_line(signals: list[str]) -> str:
    """List the signals the scan matched a modality by."""
    return "Signals: " + " | ".join(signals)


def fields_line(fields: list[str]) -> str:
    """List the fields the scan observed on a modality."""
    return "Fields observed: " + ", ".join(fields)


def exemplar_heading(location: str) -> str:
    """Introduce one verbatim excerpt, naming where it came from."""
    return f"Exemplar ({location}):"


PASSAGE_CONCEPTS_HEADING: str = "CONCEPTS EXTRACTED FROM HERE: "
DESCRIBING_MARK: str = " (the one you are describing)"
CONTEXT_SOURCE_PROFILE: str = "THE EXEMPLARS PROFILE"
CONTEXT_SOURCE_GRAPH: str = "THE SYLLABUS GRAPH"


def syllabus_blocks(domains: int, concepts: int) -> str:
    """Open the graph's evidence for the subject-context synthesis."""
    return (
        f"The syllabus is divided into {domains} block(s), with {concepts} concept(s) "
        "in total. They are called:"
    )
