EXEMPLARS_PROFILE_FIELD_NAMING = """\
- KEYS IN ENGLISH, ASCII ONLY (NON-NEGOTIABLE): the field names — the keys of the `fields` object — go in ENGLISH, in snake_case and in pure ASCII; each one must match `^[a-z][a-z0-9_]*$`. No accents, no spaces, no capitals, no hyphens: they become code identifiers.
- CANONICAL VOCABULARY: the names have to be stable across different courses, so that a programming exercise and a physics exercise are described with the same keys. If a field plays one of these roles, use EXACTLY that name instead of inventing a synonym:
  · the main text that sets the student the task, the problem or the question → `statement`
  · the answer, resolution or expected result → `solution`
  · the degree of difficulty or demand → `difficulty_level`
  · the title or short name of the exercise → `title`
  · the alternatives of a closed question → `options`
  · which of the alternatives is the correct one → `correct_answer`
  · the starting material handed to the student already written (code with a bug, a template to fill in, a text to correct, input data) → `base_material`
  · the didactic explanation or justification of the answer → `explanation`
  Invent a new name ONLY if the field's role does not appear in this list; then apply the same rules to it. Do not add suffixes describing the concrete medium of this sample: `solution`, not `solution_code`.
- RESERVED NAMES, forbidden as a field: `item_type`, `id`, `source`, `concepts`, `primary_concept`. The system itself uses them.
- NO MODALITY FIELDS: do not declare a `type`, `item_kind`, `modality`, `format` field or equivalent. The exercise's modality IS the key of its entry in `item_types`; such a field would duplicate it.\
"""


EXEMPLARS_PROFILE_SCHEMA_GRAMMAR = """\
`schema` is ALWAYS a JSON object. Never a list, never a bare string. ALL its keys go INSIDE that object; none as a sibling of `schema`. Permitted vocabulary, and no other:
- `"type"`: one of `"string"`, `"integer"`, `"number"`, `"boolean"`, `"array"`, `"object"`.
- `"type"` as a LIST of those same names, for values that admit absence: {"type": ["string", "null"]}. Inside `type` everything is a quoted TYPE NAME, `"null"` included.
- with `"type": "array"`, the key `"items"` goes INSIDE the schema: {"type": "array", "items": {"type": "string"}}. A list that may be missing combines both forms: {"type": ["array", "null"], "items": {"type": "string"}}.
- `"enum"`: a non-empty list of permitted literal VALUES (not type names), for categorical fields: {"enum": ["basic", "intermediate", "advanced"]}. ONLY here, and only if the field admits absence under the NULL POLICY, may the JSON literal `null` appear as one more value in the list.
- optional constraints, inside the same object: `"minLength"`, `"maxLength"`, `"minimum"`, `"maximum"`, `"default"`.

VALID shapes of `schema` — there is no other:
  {"type": "string"}
  {"type": ["string", "null"]}
  {"type": "array", "items": {"type": "string"}}
  {"enum": [1, 2, 3, 4]}

INVALID shapes (real mistakes already made; do not repeat them):
  ["string", "null"]                    → the wrapper is missing: it is {"type": ["string", "null"]}
  {"type": "array"} + a sibling `items` → `items` goes inside the `schema` object
  {"type": "str"} / "text" / "list"     → those type names do not exist\
"""


def scan_item_types_prompt(content: str, location: str = "", excerpt_chars: int = 400) -> str:
    where = f"\nFragment taken from: {location}\n" if location else ""
    return f"""\
Analyse a FRAGMENT of raw teaching material (exercises, problems, activities, questions) and inventory the exercise MODALITIES that appear in it.

A modality is a WAY of setting the student the task, defined by the exercise's anatomy: which pieces of information make it up. Examples of different modalities: a closed question with alternatives; a numerical problem asking for a result computed from given data; a commission to write a program from scratch; a piece of starting material (code, a text, a schematic) with a mistake to locate and correct; a practical case to analyse and solve with written reasoning.

This fragment is ONLY ONE PART of the material: do not try to describe the whole course and do not guess modalities that are not here. Inventory what you SEE in this fragment, and nothing else. A later step will gather the inventories of all the fragments.
{where}
# WHAT COUNTS AS AN EXERCISE
Any unit the material SETS THE STUDENT AS A TASK counts. These do not count: theoretical exposition, explanations and definitions, examples that illustrate an explanation without asking anything, tables of contents, unit objectives, rubrics and bibliography. If the fragment sets no task, return `{{"types": []}}`.

# TWO MODALITIES ARE THE SAME IF THEY ARE FILLED IN THE SAME WAY
The test, apply it before separating anything: would the SAME pieces of information be filled in when writing one and the other? If so, it is ONE modality, however different the document's label is.
- «Proposed exercise» and «Worked exercise» are the SAME modality: one carrying the solution and the other not is an empty field, not a new modality.
- «Basic exercise» and «Advanced exercise» are the SAME modality: difficulty is a field, not a modality.
- «Exercise 3.1» and «Exercise 7.2» are the same modality: numbering and topic do not change it.
- A question with alternatives and a commission to program ARE different modalities: the first needs a list of options and a correct answer; the second, a statement and code.
When in doubt, GROUP. Over-separating fragments the material into anecdotal modalities; over-grouping is corrected afterwards.

# WHAT YOU MUST PRODUCE
A single JSON object:

{{
  "types": [
    {{
      "key": "<key in english, snake_case, ascii>",
      "label": "<readable name of the modality, in the language of the material>",
      "signals": "<how it is recognised in the document: labels, headings, visible structure>",
      "fields": ["<field_name>", "..."],
      "excerpt": "<up to {excerpt_chars} literal characters of the most representative specimen>"
    }}
  ]
}}

- `key`: in English, `^[a-z][a-z0-9_]*$`, ASCII only. It names the MODALITY, not the topic: `multiple_choice`, `numerical_problem`, `write_code`, `fix_error`, `case_analysis`, `theory_problem`.
- `fields`: the pieces that make up THIS modality, with the canonical names below. Only the ones the fragment genuinely shows.
- `excerpt`: a LITERAL copy, trimmed to {excerpt_chars} characters, of the specimen that best represents the modality. It is what the next step will see in order to write the extraction instructions, so choose a complete and typical one, not the strangest. Escape line breaks (`\\n`) and quotes (`\\"`).

# FIELD NAMES
{EXEMPLARS_PROFILE_FIELD_NAMING}

# OUTPUT RULES
- A single JSON object. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- If the fragment sets the student no task, return `{{"types": []}}`.

<<<FRAGMENT>>>
{content}
<<<END>>>

JSON:"""


def consolidate_exemplars_profile_prompt(findings: str, max_types: int) -> str:
    return f"""\
You have received the INVENTORY of exercise modalities that a previous scan found, fragment by fragment, in all the raw teaching material of a course. Consolidate it into the definitive EXEMPLARS PROFILE.

The profile is the ONLY piece that instantiates the system for a particular course: the same engine generates programming exercises, physics problems, multiple-choice questions or case studies, but always learning material. It declares, abstractly, the anatomy of each exercise modality of this course: which fields make it up, what type they are, how they are extracted from a document and how a new one would be written.

The inventory comes from fragments analysed separately, so it BRINGS DUPLICATES: the same modality will appear with different keys, with overlapping field sets and with similar labels. Unifying them is your main job.

# WHAT YOU MUST PRODUCE
A single JSON object with EXACTLY these top-level keys:

{{
  "item_types": {{
    "<modality_key>": {{
      "label": "<readable name>",
      "description": "<what this modality is and how it is recognised>",
      "primary_field": "<name of one of its fields>",
      "embed_fields": ["<primary_field>", "<another field the student RECEIVES>"],
      "general_generation_rules": ["<rule>", "..."],
      "fields": {{
        "<field_name>": {{
          "schema": {{ "type": "string" }},
          "description": "...",
          "guidance": {{ "extraction": "..." }}
        }}
      }}
    }}
  }}
}}

# WHAT YOU MUST NOT DECLARE
Nothing about the subject itself: not the subject matter, not the educational level, not the language, not general conventions of the degree. That is written separately, in prose, in another step of the system. Here you describe ONLY the anatomy of the modalities. Do not add top-level keys: `item_types` is the only one.

# item_types — HOW MANY MODALITIES
- MERGE WITHOUT FEAR. Two inventory entries are the SAME modality if the same pieces are filled in when writing them. One carrying a solution and the other not, one being basic and the other advanced, their being in different units: none of that separates them. When merging, keep the clearest key and the UNION of their fields (the ones missing from one variant are fields that admit `null`, see NULL POLICY).
- SEPARATE ONLY WHEN THE ANATOMY CHANGES. A different modality needs fields the other has no business having, or a clearly different way of being written. Test: if the two share `fields` and their `general_generation_rules` would come out nearly identical, it is one.
- DISCARD THE ANECDOTAL. A modality appearing once in the whole corpus that fits reasonably inside another goes inside the other. Only what the material genuinely uses as a format of its own survives on its own.
- AT MOST {max_types} modalities. If you get more, you are separating by topic or by difficulty instead of by anatomy: merge again. The usual is 1-3.
- Order them from most frequent to least: the first is the one the system uses by default.

For each modality:
- `label`: its readable name, in the language of the material («Multiple-choice question», «Error correction»).
- `description`: what it is and how it is recognised. It is read both by the extractor — to decide which modality each exercise in the document belongs to — and by the generator. Be discriminating: describe what distinguishes it from the profile's other modalities, not what they have in common.
- `general_generation_rules`: how a NEW exercise of this modality is written. It is the most important part of what you produce and it has a section of its own below — read it before writing them.

# fields — WHAT THEY ARE CALLED
{EXEMPLARS_PROFILE_FIELD_NAMING}
- CONSISTENCY ACROSS MODALITIES: if two modalities have a field with the same role, it must be called THE SAME in both (`statement` in all of them, not `statement` in one and `question` in another).

# fields — WHICH ONES TO INCLUDE
One field per ESSENTIAL piece of information that makes up an exercise of that modality.

- LESS IS MORE: include the MINIMUM set of fields that fully captures an exercise. Each field has to earn its place: do NOT add speculative, redundant, derivable or merely anecdotal fields. At the same time, do NOT leave out anything essential to represent or write the exercise (at the very least, the one carrying the main semantic load). When in doubt between adding a marginal field and leaving it out, leave it out. The usual is 3-5 fields per modality.
- DERIVABILITY TEST (apply it to EACH field before including it): if its value can be computed from the other fields without looking at the document again, it is NOT a field — it is deduced, and it does not belong. Discard in particular: flags that only indicate whether another field has a value or is empty (`is_solved`, `has_solution`: that is already said by `solution` being null); counters, lengths or sizes of another field; and fields whose value is a restatement of another. If in describing a field you need to mention another field to define it, that is a near-certain sign that it is derivable.
- NO CONCEPTS AND NO TOPICS: do not declare concept, topic, subject or thematic-tag fields (`topics`, `concepts`, `keywords`…). Which curriculum concept each exercise practises is annotated downstream by the system against a knowledge graph, and such a field would overlap with that annotation. Whatever situates the course as a whole (subject, educational level, language) goes neither in `fields` nor anywhere else in this profile.
- MINIMUM COVERAGE: the profile has to suffice to (a) represent the exercise, (b) retrieve it semantically and (c) write a new PARAMETERISED one. In practice that nearly always requires: the statement carrying the semantic load (the `primary_field`, mandatory); the expected solution, when the material brings it or admits it; and at least one CLASSIFYING field that can be pinned as a parameter when asking for a new exercise (difficulty, level…). If the sample does not label that classifying axis but it is deducible by observing the exercise, declare it anyway and define the criterion (see NULL POLICY).

For each field:
- `schema`: the shape of the value.
{EXEMPLARS_PROFILE_SCHEMA_GRAMMAR}
- `description`: the intrinsic NATURE of the field (what it represents), in the subject's language of instruction.
- `guidance.extraction`: how to EXTRACT this field from a source document. **Write it in more detail and with more precision than the rest of the texts**: it feeds a later extraction process that has to be exact and deterministic, so be concrete and actionable, and lean on the literal fragments in the inventory. Cover, where they apply: what to copy and whether it goes VERBATIM or normalised; the BOUNDARIES with the neighbouring fields (what belongs to this field and what does NOT, so they do not overlap); the concrete markers or headings in the document that delimit it (e.g. "Solution:", "Proposed exercises"); what to EXCLUDE (enumeration labels, section headers, page artefacts); and, only in fields that admit absence under the NULL POLICY, when the field goes to null. It applies to every field that can be located in the material.
- `guidance.generation`: **do NOT write it. Ever.** It exists in the format, but it is a field filled in by hand by whoever administers the course when a particular field needs a nuance the rules do not cover. You leave only `extraction` in `guidance`. Whatever you know about how this modality is WRITTEN goes entirely into `general_generation_rules`.

# NULL POLICY — IT DEPENDS ON WHETHER THE FIELD IS COPIED OR DEDUCED
The question is not "does this modality usually bring this field?", but "could ONE SINGLE exercise of this modality be missing it?". The answer depends on where the value comes from, and there are two cases with OPPOSITE rules.

## Fields COPIED from the document (statement, solution, starting material, options, explanation)
They admit `null` UNLESS the exercise does not stand up without them. The only safe exception is the `primary_field`: an exercise with no statement is not an exercise. Declare a copied field mandatory only when its absence would break the whole modality: the `options` of a closed question, the code to be fixed in an error correction.

The two mistakes do NOT cost the same, and that asymmetry is the rule:
- Declaring it nullable when the content is always there costs nothing: the extractor will always fill it in, because it always finds it.
- Declaring it mandatory when it may be missing FORCES IT TO BE INVENTED. Downstream this field enters the extractor's grammar as mandatory, so faced with an exercise that does not bring it the model cannot answer "it is not there": it fabricates one, and out comes false teaching material indistinguishable from the real thing.

Two signs that do NOT prove a copied field is always present:
- The inventory not bringing a single exemplar without it. The inventory is a SAMPLE of fragments, not the whole corpus.
- What the documents are called. A whole corpus of "solutions" files typically resolves the theory part and leaves the practical part's statements bare.

## Fields DEDUCED by observing the exercise (the CLASSIFYING ones: level, category…)
Here `null` IS THE LAST RESORT, for the opposite reason: their value is not to be found in the document, it is to be judged, and it can always be judged. The document not LABELLING it explicitly is NOT a reason to admit `null`: it is a reason to define a criterion that allows it to be DEDUCED from the content itself.
- Do NOT declare it optional by default. If its value is deducible by observing the exercise, the field does NOT carry `null`.
- Its `description` must include an INTERNAL CLASSIFICATION CRITERION particular to the course: enumerate each possible value together with the OBSERVABLE SIGNALS that identify it (which constructs, what complexity, what demand or what prior knowledge the exercise presupposes). The criterion must cover ALL the material, so that any exercise can be classified without exception.
- Its `guidance.extraction` must say: if the document brings an explicit label, that one is used; if it does NOT, the criterion defined in `description` is applied to the exercise's content. NEVER "if there is no label, null".

# general_generation_rules — HOW THIS COURSE WRITES (THE PART THAT MATTERS MOST)
It is the ONLY thing the profile tells the generator about how an exercise of this modality is written. There is no second chance field by field here: whatever is not in these rules, the generator does not know. Give it more attention than any other part of the profile.

Write them looking at the inventory's `excerpt`s and asking yourself what ALL the specimens of this modality have in common. A rule is a CONVENTION OBSERVED in this material, not an opinion of yours about didactics.

- EVERY RULE MUST BE CHECKABLE. It has to be possible to read an already-written exercise and say whether it complies. «The statement must be clear» is not checkable and is not a rule; «the statement must specify the input, the output and the expected behaviour» is.
- NAME THE FIELD it applies to when the rule is about a particular field («the solution must…», «the statement must…»). There is no per-field guidance to say it for you, so the rule has to say it itself.
- COVER, when the material shows them consistently: what each written field must obligatorily contain; the NOTATION and formatting conventions particular to the course (how things are documented, which headings, which units, which symbols); the typical LENGTH and scope of a specimen; and the CONSISTENCY relations between fields (that the solution answers exactly what the statement asks, that the starting material and the solution fit together).
- NO GENERIC DIDACTICS. «It must foster critical thinking», «it must be motivating», «fit the difficulty to the level»: the generator already takes care of all that, since it knows about didactics and knows nothing about this course. You contribute the second. If a rule would hold equally for any course in the world, it does not belong.
- NO CONTENT. Do not fix the topic, the setting or the concepts of the exercises: each commission decides that against the curriculum graph. The rules talk about FORM.
- ONLY ABOUT THIS MODALITY. A rule that only makes sense here (requiring a docstring and a test block, requiring the result with its units and significant figures) goes ONLY here. If it is true of all the modalities equally, then it describes the whole course and contributes nothing in any of them.
- QUANTITY: between 3 and 8. Fewer than 3 nearly always means you have not looked at the specimens; more than 8, that you are breaking one rule into its consequences or slipping in generic didactics.

# primary_field
One per modality. The name of the field carrying the exercise's main SEMANTIC LOAD: the statement, the text that sets the student the task. Downstream it is what is compared against the curriculum graph to decide which concept each exercise practises, so it must be the field you read to know what the exercise is about. It must be one of the keys of THAT modality's `fields`.

# embed_fields
The list of fields that, TOGETHER, are read to decide which curriculum concept the exercise practises. It is a list because in some modalities the statement alone does not say what the exercise is about: in «what does the following code print?» the statement is a fixed formula and the concept is in the CODE HANDED to the student.

- ALWAYS start with the `primary_field`, and add afterwards only the fields the student RECEIVES alongside the statement and without which the exercise cannot be understood: the starting material, the code fragment to analyse, the options of a multiple-choice question.
- NEVER include the SOLUTION or the explanation of the answer. It is the answer, not the exercise: when measured, including it MADE accuracy WORSE. Do not include classifying fields either (difficulty, level): they contribute no concept and add identical noise across all exercises.
- Test: cover the field up. If, reading what remains, it can no longer be said which concept is practised, the field goes in the list. If it still can be said, it stays out.
- If the statement suffices on its own, `embed_fields` is exactly `["<primary_field>"]`.

# OUTPUT RULES
- Return ONE SINGLE JSON object. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- The field names (keys of `fields`) and the keys of `item_types` ALWAYS in English, snake_case, ASCII only. The rest of the human-facing text (`label`, `description`, `guidance`, `general_generation_rules`) in the language of the material.
- Include only the ESSENTIAL fields: less is more, but without leaving out anything indispensable. None derivable from another. `null` on every field copied from the document that may be missing in some exercise, and on no deducible one.
- Every text value on ONE SINGLE LINE: no real line breaks, no backticks and no code blocks inside the strings. Escape line breaks (`\\n`) and inner quotes (`\\"`).
- BEFORE ANSWERING, check the seven things that go wrong most: (1) the value of every `schema` is an OBJECT `{{...}}`, never a list; (2) every key of `fields` and every key of `item_types` matches `^[a-z][a-z0-9_]*$`; (3) each modality's `primary_field` is exactly one of the keys of ITS `fields`; (4) `embed_fields` starts with the `primary_field`, names only fields from ITS `fields` and does not include the solution; (5) there are no two modalities that would be filled in the same way; (6) NO `guidance` carries the key `generation`, and every modality brings between 3 and 8 checkable `general_generation_rules`; (7) every field COPIED from the document other than the `primary_field` admits `null`, unless the modality does not stand up without it.

<<<INVENTORY>>>
{findings}
<<<END>>>

JSON:"""


def repair_exemplars_profile_prompt(profile: str, error_msg: str) -> str:
    return f"""\
The following EXEMPLARS PROFILE parses as valid JSON but does not satisfy the required format. Correct it.

# VALIDATION ERROR
{error_msg}

# PROFILE TO CORRECT
{profile}

# `schema` FORMAT — the usual cause of the error
{EXEMPLARS_PROFILE_SCHEMA_GRAMMAR}

# FIELD NAMES
{EXEMPLARS_PROFILE_FIELD_NAMING}

# RULES
- Keep the original content (`label`, `description`, `guidance`, rules) as it is; correct ONLY what breaks the format. If you rename a field, rename it wherever it is referenced too.
- Exactly one top-level key: `item_types`. Nothing else at that level. If the profile brings a `content_context`, LEAVE IT where it is: it comes from an earlier version and another step migrates it; do not delete it and do not edit it.
- `item_types` is a NON-EMPTY object. Each key matches `^[a-z][a-z0-9_]*$` and its value declares at least `primary_field` and `fields`, and optionally `label`, `description` and `general_generation_rules`.
- Each modality's `primary_field` must be one of the keys of ITS OWN `fields`.
- `embed_fields`, if present, is a non-empty list without repetitions that STARTS with that modality's `primary_field` and names only keys from ITS OWN `fields`.
- Return ONE SINGLE JSON object. Nothing before, nothing after. No backticks, no comments, no explanations.

JSON:"""
