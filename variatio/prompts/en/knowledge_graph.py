"""The calls that build a knowledge graph, from one chunk of corpus to the whole syllabus.

The JSON keys they draw — `concepts`, `relations`, `merges`, `canonical`, `aliases`, `drop`,
`domains`, `non_taggable` — are English in both sets: they are the grammar `schemas.py` pins
and what the parsers read, so a translated key yields a well-formed answer that parses to
nothing. The two slots of a triple are SOURCE and TARGET in this set's prose and must match
the words `relations.py` puts in the catalogue. The rule blocks below are shared so eight
prompts cannot describe one block format in eight ways.
"""

_KG_LANGUAGE_RULE = """\
# LANGUAGE
Write the name of each concept IN THE SAME LANGUAGE as the source material. Do not translate it, do not normalise it into another language, do not transliterate it. Keep the wording, the accents and the capitalisation of the subject's terminology.
The keys of the relation types listed below are FIXED IDENTIFIERS, not words from the text: emit them exactly as written, whatever the language of the material."""


def _kg_type_preference_rule(schema) -> str:
    """Render how to choose a relation type, which turns on the schema having a fallback.

    With no catch-all relation the instruction is to emit nothing when no type clearly
    applies; with one it is to prefer the specific types and not to treat the fallback as a
    default drawer.
    """
    if schema.fallback is None:
        return (
            "- Emit a relation only when one of the types above clearly applies. If none "
            "does, do not emit the relation."
        )
    specific = ", ".join(f"`{key}`" for key in schema.specific_keys())
    return (
        f"- Prefer the SPECIFIC type ({specific}) whenever its reading is clearly true; "
        f"reserve `{schema.fallback}` for real associations that fit no other. Do not force "
        f"a specific type when in doubt, but do not use `{schema.fallback}` as a default "
        f"catch-all either."
    )


_KG_DEFINITION_RULE = """\
# ONE DEFINITION PER CONCEPT
Each concept carries a ONE-sentence DEFINITION, taken from how the passage itself explains it: what it is, in the subject's own terms. It is what will later allow two similar names to be told apart and what is taught before what to be decided, so it has to name the idea and not the example.
- A single sentence, 10 to 25 words, impersonal (no «the student», no «you learn to»).
- It says WHAT IT IS, not what it is used for in the exercise or what tool it is done with.
- If the passage only mentions the concept without explaining it, a minimal definition is enough; do not invent detail the text does not give."""


_KG_EXTRACT_OUTPUT = """\
# OUTPUT
A single JSON object with exactly this shape:
{
  "concepts": [{"name": "<concept>", "definition": "<one sentence>"}, "..."],
  "relations": [["<source>", "<type>", "<target>"], "..."]
}
- The `<type>` is one of the identifiers listed above. Nothing else.
- Every source and every target in `relations` is written with the EXACT name of the concept."""


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
            "\n# WHERE THIS PASSAGE SITS IN THE MATERIAL\n"
            f"{location}\n"
            "It is the heading path of the section the passage was taken from. Use it to tell "
            "what the section is ABOUT from what it only mentions in passing, and to name the "
            "concepts the way this part of the syllabus names them — the neighbouring passages "
            "of this same section are being read under this same heading, so their names have "
            "to come out identical to yours.\n"
        )

    return f"""\
Extract a KNOWLEDGE GRAPH from a passage of teaching material of ANY subject. Identify the CONCEPTS of the subject and the TYPED RELATIONS between them, directly in the schema given below.
{location_block}

# WHAT COUNTS AS A VALID CONCEPT
A concept NAMES an idea of the subject: a term that could be an entry in a glossary or an index (a thing, technique, category, structure, phenomenon or named entity). It is NOT a sentence describing or predicating something.
- The glossary test: if you would NOT put it as an entry in an index of the subject, it is NOT a concept.
- Do NOT extract: document metadata (section titles, bibliography, licences, authors), incidental settings from the examples (concrete objects, characters or situations that only illustrate), or fragments that read as part of a sentence (they start with a verb, contain a conjugated verb, or express a condition or an action).

# NAMING CANON (CRITICAL)
This passage is one of hundreds extracted separately from the same corpus, and the results are merged BY NAME. Two passages naming the same idea differently produce two concepts that will never be reconciled, so do not name what this passage happens to say — name what the subject's index would say.
- SINGULAR always, even if the passage speaks in the plural.
- NOUN form, never the adjective or the quality: name the thing, not its property.
- No articles, no determiners, no possessives.
- No nuance taken from the example, the exercise or the tool of the moment: name the concept and stop there.
- Keep the wording the teaching material itself uses for the idea when it has one; do not translate it, do not modernise it, do not expand an abbreviation the material keeps short.
- The same idea must come out with the SAME name always, whichever passage it appears in.

{_KG_DEFINITION_RULE}

{_KG_LANGUAGE_RULE}

# RELATION TYPES (respect the direction SOURCE → TARGET)
Each relation is a triple [source, type, target]. The direction matters: choose the order that makes the stated reading true.
{schema.catalog_block()}

# RELATION RULES
- The source and the target must be DIFFERENT, and both must appear in your `concepts` list. Relating a concept to itself is forbidden.
{_kg_type_preference_rule(schema)}
- Extract only the relations SUPPORTED by the passage's text, not by outside knowledge.
- Be exhaustive with the relations: when the passage explains one concept by leaning on another, that is a relation to state, even if the text does not phrase it as one. Two concepts on your list that the passage treats together with no relation between them is, almost always, a missing relation.

{_KG_EXTRACT_OUTPUT}
- If the passage yields no extractable concept, return {{"concepts": [], "relations": []}}.
- No text before or after, no backticks, no comments.

# PASSAGE
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
    location_line = f"Section: {location}\n" if location else ""
    found_concepts = "\n".join(
        f"- {name} — {definitions[name]}" if definitions.get(name) else f"- {name}"
        for name in concepts
    )
    found_relations = (
        "\n".join(f'- ["{s}", "{k}", "{t}"]' for s, k, t in relations) or "- (none)"
    )
    return f"""\
A first reader extracted from this passage of teaching material the concepts and typed relations listed below. A first reading ALWAYS falls short: it names the obvious, states few relations and stops.

Your task: a SECOND reading of the same passage returning ONLY what is missing — concepts of the subject the first reader did not name and, above all, RELATIONS the text supports between already-named concepts that do not appear in the list.
{location_line}
# WHAT TO LOOK FOR
- Relations between two ALREADY LISTED concepts that the passage treats together: when it explains one by leaning on the other, when one is a case or a part of the other, when the text presents them in sequence. Go through the concept list two at a time and ask yourself whether the text relates them.
- Concepts the passage explains (not merely mentions in passing) that are not in the list. Apply the glossary test: if it would not be an entry in an index of the subject, it is not a concept.
- Name the new concepts with the first reader's canon: SINGULAR, noun form, no articles, no nuance from the example, and with the same wording the material itself uses.
- Reuse the already-listed names EXACTLY when a relation mentions them. Do not rewrite them, do not correct them, do not translate them.

{_KG_DEFINITION_RULE}

{_KG_LANGUAGE_RULE}

# RELATION TYPES (respect the direction SOURCE → TARGET)
{schema.catalog_block()}

# RELATION RULES
- The source and the target must be DIFFERENT and both must be in the already-known list or in your `concepts` list.
{_kg_type_preference_rule(schema)}
- Extract only the relations SUPPORTED by the passage's text, not by outside knowledge.
- Do NOT repeat anything already listed: neither concepts nor relations. Only what is new.

{_KG_EXTRACT_OUTPUT}
- `concepts` carries ONLY the new concepts; the already-known ones may be used in `relations` without listing them again.
- If nothing is genuinely missing, return {{"concepts": [], "relations": []}}.
- No text before or after, no backticks, no comments.

# CONCEPTS ALREADY EXTRACTED
{found_concepts}

# RELATIONS ALREADY EXTRACTED
{found_relations}

# PASSAGE
{source_text}

JSON:"""


_KG_TEACHING_ORDER_RULE = """\
# THE TEACHING ORDER IS WHAT MATTERS
Passage-by-passage extraction only sees a dependency when two concepts are explained at once, which is exactly when the material does NOT need to state it. The order of the syllabus is therefore almost entirely missing, and recovering it is the main reason this step exists.
- Go through the concepts asking yourself, for each one: what must a student ALREADY understand before this can be taught? Every answer that is itself in the list is a relation to propose.
- A dependency is real even if the two concepts have never appeared together: their being far apart in the material is evidence FOR proposing it here, not against.
- Most concepts of a subject lean on something. A concept with nothing before it should be the exception — the genuine starting points — and not the norm.
- Do not chain what is already implicit: state the DIRECT dependency, not the whole ancestry. If A leans on B and B on C, do not also relate A to C.
- Being cautious is not free here: a dependency you leave out is one no later step can recover.
- Prefer BOTH ends to be things a student is taught and could be examined on. The extraction also picked up tools, notation and vocabulary of the document; an order hanging off that describes the material and not the syllabus, and nothing downstream can use it. When a dependency is real but one of the ends is such a term, look for the taught concept behind it and relate that one."""


_KG_MATERIAL_ORDER_RULE = """\
# THE ORDER OF THE LIST IS THE ORDER OF THE MATERIAL
The concepts are listed in the ORDER IN WHICH THE MATERIAL INTRODUCES THEM, from the start of the corpus to the end. Whoever wrote the material already decided a teaching order, and that order is the best evidence you have:
- A concept leans, almost always, on concepts that come BEFORE it in the list. For each one, look upwards and ask yourself which of the earlier ones a student has to know already.
- Proposing that a concept leans on another that comes AFTER it in the list is claiming the material teaches it in the wrong order. It may be true — a textbook sometimes brings a consequence forward — but it demands that the dependency be unambiguous; when in doubt, respect the material's order.
- Distance in the list is not an obstacle: what comes first in the corpus is the foundation of almost everything that follows, and those long dependencies are precisely the missing ones.
- Each concept carries, when it is known, a one-sentence definition taken from the material. Judge the dependency on the definition, not on the similarity of the names."""


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
You are given the concepts of ONE syllabus block, «{domain}», of a knowledge graph built from the teaching material of a single course. Each concept is listed with the relations already known about it, as evidence.

Your task: propose the TYPED RELATIONS that are MISSING between the concepts of this block — above all the order in which they have to be taught.

{_KG_LANGUAGE_RULE}

# RELATION TYPES (respect the direction SOURCE → TARGET)
{schema.catalog_block()}

# RULES
- The source and the target must be DIFFERENT and both must appear LITERALLY in the list below. Do not invent concepts, do not rewrite their names and do not relate a concept to itself.
- Do NOT repeat a relation already shown as evidence. Only what is missing.
{_kg_type_preference_rule(schema)}

{_KG_TEACHING_ORDER_RULE}

{_KG_MATERIAL_ORDER_RULE}

# OUTPUT
A single JSON object with exactly this shape:
{{
  "relations": [["<source>", "<type>", "<target>"], "..."]
}}
- The `<type>` is one of: {schema.key_list()}.
- If nothing is missing, return {{"relations": []}}.
- No text before or after, no backticks, no comments.

# CONCEPTS OF «{domain}», IN THE ORDER OF THE MATERIAL (with their definition and the relations already known)
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
You are given the concepts of a knowledge graph built from the teaching material of a single course, grouped into the SYLLABUS BLOCKS of the syllabus. The relations inside each block have already been proposed.

Your task: propose ONLY the TYPED RELATIONS that CROSS from one block to another — the framework that orders the syllabus as a whole and that no reading of a single block could reveal.

{_KG_LANGUAGE_RULE}

# RELATION TYPES (respect the direction SOURCE → TARGET)
{schema.catalog_block()}

# RULES
- The source and the target must belong to DIFFERENT BLOCKS. A relation between two concepts of the same block will be discarded: that is not what this step is for.
- Both must appear LITERALLY in the lists below. Do not invent concepts and do not rewrite their names.
{_kg_type_preference_rule(schema)}

{_KG_TEACHING_ORDER_RULE}

{_KG_MATERIAL_ORDER_RULE}
- Work block by block: for each one, ask yourself which concepts of the EARLIER blocks it leans on. The blocks also come in the order the material presents them, and inside each block its concepts follow that same order.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "relations": [["<source>", "<type>", "<target>"], "..."]
}}
- The `<type>` is one of: {schema.key_list()}.
- No text before or after, no backticks, no comments.

# SYLLABUS BLOCKS AND THEIR CONCEPTS, IN THE ORDER OF THE MATERIAL (each concept with its definition)
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
You are given SMALL GROUPS of node names from a knowledge graph automatically extracted from a corpus of teaching material, each name with its outgoing relations as evidence. The extraction was passage by passage and each passage named things in its own words, so the SAME idea arrives several times dressed in different grammar. The groups were formed ONLY by name similarity, which is a suspicion, not a verdict: many groups contain names that merely resemble each other and must be left alone.

Your task: within EACH group, and never across groups, decide which names are THE SAME CONCEPT and must be merged into one.

# THE MERGE TEST: ONE GLOSSARY ENTRY, ONE CONCEPT
- Would an index of the subject give these names ONE entry or TWO? If one, merge them, however different their grammar.
- Merge across grammatical form: the adjective, the noun and the quality of the same idea are a single concept; so are the singular, the plural and the plural noun phrase; and so are a term and that same term with the object it applies to stuck on the end.
- Merge a term with its own definition used as a name: when one name states the idea and another spells out that same idea as a longer phrase, they are a single concept.
- Do NOT merge two ideas a student could be examined on separately, even if they always appear together: a mechanism and the technique that uses it stay apart, and so do a part and the whole it belongs to, and so do a general term and one of its concrete kinds.
- Do NOT merge two names merely because they belong to the same topic, are related or often appear together. Sharing a word is not evidence.
- Use the relations as evidence: names with clearly different relations are usually different concepts.
- When a name carries after « — » a definition taken from the material, read it as evidence of WHICH idea it names, not as proof that it is another concept: each fragment defined its own in its own words, so two different wordings of ONE idea are the normal case and are a single concept; they are two concepts only when they define ideas a student could be examined on separately, however alike the names.
- A grammatical variant of the same name — singular and plural («Use cases» and «Use case»), capitalisation, an extra article or preposition — is ALWAYS a single concept, whatever the definitions beside them say.
- Over-merging costs more than under-merging: a concept lost in a merge is not recovered afterwards. When the two readings are equally defensible, leave them apart.

# CANONICAL NAME
- The canonical one MUST be one of the names of its own group, copied exactly. Do not invent names, do not translate them, do not correct their spelling.
- Prefer the shortest form that still names the idea completely, and the one written as a noun.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "merges": [{{"canonical": "<name>", "aliases": ["<name>", "..."]}}, "..."]
}}
- One entry per set of names that ARE the same concept. Names that merge with nothing simply do not appear.
- Never put names from two different groups in the same entry.
- If nothing merges in any group, return {{"merges": []}}.
- No text before or after, no backticks, no comments.

# GROUPS
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
You are given part of the NODES of a knowledge graph automatically extracted from a corpus of teaching material of a single course, each one with its outgoing relations as evidence. The extraction is noisy: alongside the subject's concepts it picked up metadata, incidental settings and sentence fragments.

Your task: list the nodes that do NOT name a concept of the subject and have to be removed. Everything you do not list is kept.

# WHAT COUNTS AS A VALID NODE
A valid node NAMES a concept of the subject: a term that could be an entry in a glossary or an index (a thing, idea, technique, category, structure, phenomenon or named entity). It is NOT a sentence describing, explaining or predicating something.

# REMOVE
- Document metadata: section titles, bibliography, licences, authors, layout
  elements.
- Fragments that are not noun phrases: anything starting with a verb, carrying a
  conjugated verb, or stating a condition or an action.
- Single letters, isolated symbols and bare values.
- The objects, characters or settings of the illustrative examples, which belong to the
  example and not to the subject.

Judge only whether the string NAMES something. Whether what it names works as an exercise
LABEL is another question, asked later and with the exemplars profile in front of you; do
not answer it here. An umbrella term, a cross-cutting quality or a generic stage of the work
DO NAME something, so they stay.

# KEEP
- Do not remove a term for being short, elementary, generic or infrequent. Rarity is not evidence of noise here, and whether a concept works as a LABEL is decided much later by another step — that is not your question.
- When a node names something of the subject, however slight, keep it.

# WHEN IN DOUBT
- When a node carries after « — » a definition taken from the material, read it: an awkward name with a definition stating an idea of the subject is a concept and it stays.
- The glossary test: if you would NOT put it as an entry in an index of the subject, remove it.
- Faced with a FRAGMENT, remove even in doubt. Faced with a CONCEPT, keep even in doubt.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "drop": {{"<node>": "<why it does not name a concept, 10 words maximum>"}}
}}
- The keys are EXACT names from the list below. Do not invent, do not rename, do not translate and do not correct the spelling.
- Judge only the nodes listed here. If they are all concepts, return {{"drop": {{}}}}.
- No text before or after, no backticks, no comments.

# NODES
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
You are given the TABLE OF CONTENTS of a corpus of teaching material of a single course: all its headings, in the exact order in which they appear in the material and numbered from 1.

Your task: say which headings OPEN a TEACHING UNIT — a topic, a module, a large block of the syllabus — and what each one is called.

# WHAT A UNIT IS
- It is a LARGE divider of the content: what a teacher would call a topic, a module or a block. It is not a subsection, not an example, not an exercise.
- A heading that already carries an ordinal in its name («Topic I», «Unit 3», «Module II») almost always opens one, and it is the most reliable signal there is in a table of contents.
- FEW: between 3 and 12 in total. If you are naming more than a dozen, you are splitting by subsection and not by topic.
- The cover, the table of contents, the bibliography, the acknowledgements, the appendices and the course notes do NOT open a unit.

# THE ORDER IS THE ONE YOU ARE GIVEN
- The table of contents already comes in the order of the material, which is the order it is taught in. Do NOT reorder it, do not reorganise it by difficulty and do not group it by thematic affinity. Your output is sorted by `opens_at`, so any reordering you attempt is discarded.
- Everything from the heading that opens a unit to the one that opens the next BELONGS to that unit. That is why it is enough to say where each one starts.

# NAMES
- The unit's name may be the heading itself, cleaned up: without the ordinal, without trailing colons or stray dashes. If the heading does not say what it is about, write a short descriptive name yourself, IN THE SAME LANGUAGE as the table of contents.
- Do not repeat a name and do not write two names for the same block.
- FORBIDDEN a generic catch-all name such as «Other», «Various», «Miscellaneous» or «Unclassified»: everything between two units already belongs to the first.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "units": [{{"name": "<name of the unit>", "opens_at": <line number in the table of contents>}}, "..."]
}}
- `opens_at` is the NUMBER in front of the heading in the table of contents below. Do not invent numbers and do not write the heading in its place.
- No text before or after, no backticks, no comments.

# TABLE OF CONTENTS OF THE CORPUS
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
            "\n# THE DOCUMENTS THE CORPUS IS MADE OF\n"
            f"{documents_block}\n"
            "Each document is listed under a code with the title it gives itself; the titles "
            "nearly every document repeats (the course header, the fixed section names) have "
            "already been removed, so what remains is what tells one document from another. "
            "Each concept below carries in brackets the codes of the documents it was "
            "extracted from.\n"
        )
        sources_rule = (
            "\n- START FROM THE DOCUMENT TITLES: the teaching material is already organised by "
            "topic, so a title naming a syllabus block is a valid domain name, and the concepts "
            "extracted from that document are its natural members. They are a STARTING POINT, "
            "not a constraint: merge several documents into one domain, split a document "
            "covering several blocks, rewrite a title that describes a document instead of a "
            "topic, and ignore any title that names no topic at all."
        )

    return f"""\
You are given the already-cleaned CONCEPTS of a knowledge graph. They come from a single corpus of teaching material of one course.

Your task: NAME the thematic DOMAINS the subject is made of. You are NOT placing the concepts — each one will be assigned to one of your domains afterwards, in small batches. Name the blocks and nothing else.
{sources_block}
# DOMAINS
- A domain is a syllabus block of the subject (in the style of the main topics or units of a syllabus), not a fine-grained label.
- Propose FEW domains (as a guide, between 3 and 8), each covering a reasonable mass of the concepts below.{sources_rule}
- BETWEEN THEM THEY MUST COVER THE WHOLE LIST: read it to the end and check that every concept would have an obvious domain to go to. A concept none of your domains would receive means a block is missing.
- NO CATCH-ALL: it is FORBIDDEN to create a generic catch-all domain such as «Other», «Various», «Miscellaneous» or «Unclassified». Every concept has a topic, and a domain that names no topic can receive none.

# NAMES
- The DOMAIN NAMES are yours to write: short and descriptive, IN THE SAME LANGUAGE as the concepts.
- Do not repeat a name, and do not write two names for the same block.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "domains": ["<Domain name>", "..."]
}}
- Only the domain names: a handful of strings, nothing else.
- Do NOT list the concepts and do NOT write which concept goes where. That is a later question, and anything you write here about it is discarded.
- No text before or after, no backticks, no comments.

# CONCEPTS
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
The concepts of a knowledge graph built from the teaching material of a single course have already been grouped into thematic domains. The concepts below WERE LEFT OUT of that grouping — not because they are wrong, but because they were overlooked.

Your task: place EACH concept below in ONE of the EXISTING domains.

# RULES
- The domain names are FIXED. Use them exactly as written. Do NOT create new domains, do NOT rename them, do NOT leave any concept out.
- Each concept below must appear exactly once in the output.
- Assign by topic and by the evidence of the relations: the domain that already contains the concepts this one relates to is nearly always the right one. The definition accompanying each concept, after « — », says what it is about when the name does not suffice.
- There is no «other» and no «unclassified»: if a concept seems to fit none, choose the one it is LEAST alien to.
- Use the EXACT names from the input. Do not invent, do not rename, do not translate and do not correct the spelling.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "domains": {{"<existing domain name>": ["<concept>", "..."]}}
}}
- Only the domains that receive at least one concept need to appear.
- No text before or after, no backticks, no comments.

# EXISTING DOMAINS AND WHAT THEY ALREADY CONTAIN
{domains_block}

# CONCEPTS TO PLACE (with the relations already known)
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
    context_section = f"\n# TEACHING CONTEXT\n{context_block}\n" if context_block.strip() else ""
    samples_section = (
        "\n# REAL EXERCISES FROM THIS COURSE'S MATERIAL (what an exercise looks like here)\n"
        f"{samples_block}\n"
        if samples_block.strip()
        else ""
    )
    return f"""\
You are reviewing ONE thematic domain of a knowledge graph built from a corpus of teaching material of a single course. The graph exists in order to LABEL exercises (problems, assessment tasks), and a label answers exactly one question: what does that exercise make whoever solves it PRACTISE?

Your task: decide which of the concepts listed below are USELESS AS A LABEL and have to be excluded from the tagging. Everything you do not list goes on working as a label.
{context_section}
# WHAT AN EXERCISE IS IN THIS INSTANCE
This course sets its tasks in these modalities, and every label you keep will be used to label
exercises OF THESE SHAPES and no other. A concept no exercise of these modalities could ever be
about is useless as a label here, however respectable it is as a term.
{modalities_block}
{samples_section}
# THE TEST: DOES IT DISCRIMINATE?
For each concept, in this order:
1. Could an exercise have THIS concept as its objective — one a student who has mastered everything else except this one could NOT solve? If not, exclude it.
2. Could this same label be attached, without lying, to exercises practising clearly different things from different parts of the syllabus? If so, exclude it.
A label that fits almost everything says nothing at all.

# EXCLUDE
- One of any two concepts of this domain that would end up labelling THE SAME exercises — the ones no exercise could tell apart because what one practises the other practises. Keep the one a teacher would write on the exam, exclude the other. (An excluded concept remains in the graph through its relations.)
- The course, the subject or the discipline itself, its units, and the umbrella terms that only name a part of the syllabus.
- Generic activities or stages of the work: writing, running, designing, analysing, testing, documenting, maintaining, solving and the like.
- Cross-cutting qualities and virtues: quality, efficiency as a virtue, readability, correctness, usefulness — unless the corpus treats it as a technical object with content and criteria of its own.
- Vocabulary of the MATERIAL rather than of the subject: concept, technique, notation, example, summary, recommended reading, introduction, beginning, end, section titles.
- Languages, tools, platforms, libraries, standards and their names — unless the subject has them as an object of study in their own right: if an exercise in these modalities can BE ABOUT one of them, and not just about something done with it, it is a concept and it stays.
- A parent term whose specific children are also on the list and which contributes nothing beyond them.
- Single letters and symbols, isolated values, and the objects, characters or settings of the illustrative examples.

# KEEP
- Any technique, structure, mechanism, operation, rule or phenomenon specific to the subject, EVEN IF elementary: elementary is not the same as generic. An exercise can be about it.
- Everything a student can be asked to apply, build, trace, compare, choose between options or correct.
- Do not exclude a concept for being short, frequent or a prerequisite of many others: what matters is whether an exercise can BE ABOUT it, not how many times it is used as a tool.

# WHEN IN DOUBT, EXCLUDE
An excluded concept remains in the graph and goes on doing its job through its relations (prerequisites, hierarchy, composition); it is simply never used as a label. A kept concept that does not discriminate pollutes the tagging of the whole corpus.

# OUTPUT
A single JSON object with exactly this shape:
{{
  "non_taggable": {{"<concept>": "<why it does not discriminate, 12 words maximum>"}}
}}
- The keys are EXACT names from the list below. Do not invent, do not rename, do not translate and do not correct the spelling.
- Judge only the concepts of this domain. If they all discriminate, return {{"non_taggable": {{}}}}.
- No text before or after, no backticks, no comments.

# DOMAINS OF THE SUBJECT (context: this is the whole syllabus)
{domains_block}

# CONCEPTS OF THE DOMAIN «{domain}» (with their outgoing relations as evidence)
{nodes_block}

JSON:"""
