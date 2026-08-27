def describe_domain_concepts_prompt(
    domain: str,
    concepts_block: str,
    passages_block: str,
    context_block: str,
    domains_block: str = "",
    existing_block: str = "",
) -> str:
    existing_section = (
        "\n# DESCRIPTIONS ALREADY WRITTEN FOR THIS SAME BLOCK (do NOT rewrite them)\n"
        "These concepts already have a description and they are not yours to touch. They are here because they compete against yours: "
        "none of the ones you write may overlap with these. Do not copy their structure or their voice.\n"
        f"{existing_block}\n"
        if existing_block.strip()
        else ""
    )
    context_section = f"\n# TEACHING CONTEXT\n{context_block}\n" if context_block.strip() else ""
    domains_section = (
        f"\n# THE WHOLE SYLLABUS (context: the other blocks exist and have their own concepts)\n{domains_block}\n"
        if domains_block.strip()
        else ""
    )
    passages_section = (
        "\n# THEORY MATERIAL (VERBATIM) AND WHICH CONCEPTS CAME OUT OF EACH PASSAGE\n"
        "Each passage is shown ONCE, with the list of this block's concepts that were extracted from it.\n"
        "- It is the only evidence of what these concepts mean IN THIS COURSE: take the vocabulary, the notation and the level from here.\n"
        "- A passage that produced SEVERAL concepts is about one of them and mentions the others in passing. That is precisely the trap: do not describe them all with the passage's subject. Ask yourself, for each one, what IT does here that the others do not.\n"
        "- A concept with no passage is described from its name, its relations and the syllabus.\n\n"
        f"{passages_block}\n"
        if passages_block.strip()
        else ""
    )
    return f"""\
You are writing, ALL AT ONCE, the descriptions of a group of concepts from the syllabus block «{domain}».
{context_section}{domains_section}{passages_section}{existing_section}
# WHAT THESE DESCRIPTIONS ARE FOR
Each description is the surface against which it will be decided, for every exercise in the teaching material, WHICH CURRICULUM CONCEPT that exercise PRACTISES. It is compared semantically against the statements of the exercises, so each one must READ LIKE the statement of an exercise on that concept, or like its first sentence — not like the textbook definition of the concept.

Describe THE TASK that is practised: the observable thing that has to be done, not the theory behind it.

# WHY THEY ARE ALL WRITTEN TOGETHER (THE MOST IMPORTANT PART)
These descriptions are going to COMPETE with each other: they are all compared against the same exercise and only one should fit. Writing them at once exists so that you can separate them, and that is your main task.

- No description may describe another concept in this same list equally well. If two of yours would fit the same exercise, both are wrong.
- FORBIDDEN to write two descriptions with the same structure changing one word. If you catch yourself writing «Detect and correct…» and «Identify and correct…», delete both and start from what separates them.
- When two concepts are facets of one task — the part and the whole, the mechanism and its use, two variants of the same algorithm — each description states EXACTLY its own facet and takes the other for granted.
- Share out the vocabulary: a term that serves several concepts in the list distinguishes none of them. Spend the specific words on the concept they genuinely belong to.

# LEARNING OBJECTIVE, NOT TOOL (CRITICAL)
An exercise USES many concepts and PRACTISES only one or two. Each description must fit the exercises whose OBJECTIVE is that concept — the ones a student could not solve without mastering it — and NOT the ones that merely employ it in passing as a vehicle for practising something else.

- If a sentence would describe an exercise where the concept is mere support equally well, it does not belong.
- Write what the exercise DEMANDS, not what the exercise contains.
- For umbrella or trunk concepts with few details of their own, prefer a VERY SHORT, sober description with the only thing that distinguishes them. Better 1 specific sentence than 4 generic ones.

# VOICE (CRITICAL)
Each description states the task IMPERSONALLY, starting with a bare verb: «Sort…», «Compute…», «Rewrite…».
- FORBIDDEN to name anybody: no «the student», no «the learner», no «whoever solves it», no «you», no «you are asked to», no «the exercise asks».
- FORBIDDEN to talk about yourself or about this task: no «this description», «the concept being described», «in this case».
- Not a word of deliberation, no alternatives, no justification: only the descriptions, already decided.

# FORM RULES
- 1-3 sentences each, as many as it takes to be specific without falling into the generic.
- A statement of a task, not a formal definition.
- Use the terms, symbols, syntax and constructs that would genuinely appear in exercises of this course at this level. Whatever does not apply to this subject, do not use.
- Language: the language of instruction the teaching context indicates. If it cannot be inferred clearly, the language of the concept names.
- Plain text with no markup at all: no markdown, no tags, no fences (backticks, code fences, wrapping quotes).

# OUTPUT
A single JSON object with exactly this shape:
{{"descriptions": {{"<exact concept name>": "<its description>"}}}}
- ONE entry per concept in the list below, not one more and not one fewer.
- The keys are the EXACT names from the list. Do not invent, do not rename, do not translate and do not correct the spelling.
- Nothing before or after, no backticks, no comments.

# CONCEPTS OF «{domain}» TO BE DESCRIBED (with their relations in the graph)
{concepts_block}

JSON:"""


def concept_description_prompt(
    concept: str,
    domain: str,
    relations: dict[str, list[str]],
    siblings: dict[str, str],
    context_block: str,
    passages: list[dict] | None = None,
    name_documents: bool = False,
) -> str:
    context_section = f"\n# TEACHING CONTEXT\n{context_block}\n" if context_block.strip() else ""

    relations_block = ""
    relations_with_neighbors = {v: ns for v, ns in relations.items() if ns}
    if relations_with_neighbors:
        relations_lines = "\n".join(
            f"- {verbose}: {', '.join(neighbors)}."
            for verbose, neighbors in relations_with_neighbors.items()
        )
        relations_block = f"\n# RELATIONS IN THE CURRICULUM GRAPH\n{relations_lines}\n"

    siblings_block = ""
    if siblings:
        sibling_lines = []
        for name, text in siblings.items():
            written = " ".join((text or "").split())
            sibling_lines.append(f"- {name}: {written}" if written else f"- {name}")
        siblings_block = (
            "\n# OTHER CONCEPTS FROM THE SAME SYLLABUS BLOCK\n"
            "Your description competes with these: they are all compared against the same exercise and only one should fit. "
            "The ones already written are shown with their text.\n"
            "They are here ONLY so that you do not overlap with them. Do not copy their structure, their voice or their formulas: "
            "if one of them breaks the form rules below, do not imitate it — the rules outrank the example.\n"
            + "\n".join(sibling_lines)
            + "\n"
        )

    # The corpus anchoring: the paragraphs of the theory material this concept came from.
    # Without them the model describes from memory and drags in the vocabulary of its own
    # training. The document name is only given when the corpus has more than one.
    passages_block = ""
    if passages:
        cited = []
        for entry in passages:
            place = entry.get("location") or ""
            if name_documents:
                place = " · ".join(p for p in (entry.get("document") or "", place) if p)
            cited.append((f"[{place}]\n" if place else "") + (entry.get("text") or "").strip())
        passages_block = (
            "\n# WHERE THIS CONCEPT COMES FROM (THEORY MATERIAL, VERBATIM)\n"
            "The passages of the syllabus in which it appears. They are the only evidence of what this concept means IN THIS COURSE:\n"
            "- Take the vocabulary, the notation and the level from here; whatever is not here and does not follow from the teaching context, do not invent.\n"
            "- If your idea of the concept does not match what the material says, the material wins.\n"
            "- Do not quote them and do not summarise them: describe the TASK that is practised with this.\n\n"
            + "\n\n---\n\n".join(cited)
            + "\n"
        )

    return f"""\
You are generating the description of the curriculum concept «{concept}», from the syllabus block «{domain}».
{context_section}{passages_block}{relations_block}{siblings_block}
# OBJECTIVE
This description is the surface against which it will be decided, for every exercise in the teaching material, WHICH CURRICULUM CONCEPT that exercise PRACTISES. It is compared semantically against the statements of the exercises, so it must READ LIKE the statement of an exercise on this concept, or like its first sentence — not like the textbook definition of the concept.

Describe THE TASK that is practised: the observable thing that has to be done, not the theory behind it.

# LEARNING OBJECTIVE, NOT TOOL (CRITICAL)
An exercise USES many concepts and PRACTISES only one or two. The description must fit the exercises whose OBJECTIVE is this concept — the ones a student could not solve without mastering it — and NOT the ones that merely employ it in passing as a vehicle for practising something else.

- If a sentence would describe an exercise where this concept is mere support equally well, it does not belong.
- Write what the exercise DEMANDS, not what the exercise contains.

# DISTINCTIVENESS (CRITICAL)
- The description must fit ONLY exercises that practise this concept in particular, not any exercise in the subject.
- Avoid the subject's cross-cutting vocabulary — words and turns of phrase that would naturally appear in exercises on many different concepts. Work out which lexicon is common to the whole syllabus (what you would use to describe the course in general, or to describe any of the "other concepts from the same block") and do NOT use it.
- Do not use generic concrete examples: typical placeholders, filler data or neutral scenarios that appear in exercises on several different concepts. If you give an example, make it one whose statement would ONLY make sense if the learning objective were this one.
- For umbrella or trunk concepts with few details of their own, prefer a VERY SHORT, sober description mentioning only what distinguishes them from their sibling concepts. Better 1 specific sentence than 4 generic sentences.
- If what you have written would also describe a sibling concept, REWRITE it or CUT it until it does not.
- Read the siblings' already-written descriptions before answering. If yours overlaps with one, the overlap is the error: keep only what this concept has and that one does not. When two siblings are facets of one task (the part and the whole, the mechanism and its use), describe EXACTLY your facet and take the other for granted.

# VOICE (CRITICAL)
The description states the task IMPERSONALLY, starting with a bare verb: «Sort…», «Compute…», «Rewrite…».
- FORBIDDEN to name anybody: no «the student», no «the learner», no «whoever solves it», no «you», no «you are asked to», no «the exercise asks».
- FORBIDDEN to talk about yourself or about this task: no «this description», «the concept being described», «in this case».
- Not a word of deliberation, no alternatives, no justification of what you write: only the description, already decided.

# FORM RULES
- 1-4 sentences, as many as it takes to be specific without falling into the generic.
- A statement of a task, not a formal definition.
- Lean on the theory material, the teaching context and the relations to infer the register, the level and the surface vocabulary of the subject — terms, symbols, syntax, formulas, identifiers or characteristic constructs that would genuinely appear in exercises of that course at that level. Whatever does not apply to this subject, do not use.
- Language: the language of instruction the teaching context indicates. If it cannot be inferred clearly, use the same language as the concept names.
- Plain text with no markup of any kind: no markdown, no structured tags, no fences (backticks, code fences, wrapping quotes).

# OUTPUT
A single JSON object: {{"description": "…"}}. Nothing before, nothing after.

JSON:"""
