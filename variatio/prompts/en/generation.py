"""The generator's prompt: one new exercise, written against the curriculum frontier.

The stance is didactic expertise and not a teacher persona. The solver and the requester are
two roles kept apart and the requester may be either of them, so the exercise addresses
whoever is going to solve it and never speaks with a classroom voice.
"""

# A deliberate second copy of the catalogue's labels: `admissibility` imports `prompts`, so
# importing it back here would close a cycle, and `test_the_prompt_labels_match_the_catalog`
# is what keeps the two from drifting. The KEYS are the catalogue's and never translate;
# only what is shown to the model does.
_SLOT_LABELS = {
    "ambito": "Setting",
    "elementos": "Elements of the statement",
    "extension": "Length",
    "datos": "Specific data",
}


def _already_used_block(already_generated: list[str]) -> str:
    """Render the statements this commission has already produced, as settings to avoid."""
    if not already_generated:
        return ""
    existing_lines = "\n".join(f"- {s.strip()[:240]}" for s in already_generated)
    return (
        "\n# SETTINGS ALREADY USED\n"
        "Statements already produced in this same commission or saved earlier in this course "
        "on these concepts. Yours is set in a setting different from all of them:\n"
        f"{existing_lines}\n"
    )


def _request_section(requests, instructions: str) -> str:
    """Render what the requester asked for, typed by slot when the judge has screened it.

    With a `Ruling` in hand each admissible request is one line under its slot's label; with
    none the free text travels verbatim, which is where the admissibility judge failing open
    lands.
    """
    if requests:
        lines = "\n".join(f"- {_SLOT_LABELS[r.slot]}: {r.text}" for r in requests if r.slot)
        return (
            "\n# REQUEST FROM WHOEVER IS ASKING FOR THE EXERCISE\n"
            "Preferences about the wrapping and the surface of the statement. Attend to all of them; "
            "they do not touch the objective, the prior knowledge or the curriculum:\n"
            f"{lines}\n"
        )
    if not instructions.strip():
        return ""
    return (
        "\n# REQUEST FROM WHOEVER IS ASKING FOR THE EXERCISE\n"
        "A free instruction from whoever is asking for the exercise. Attend to it: if it fixes the "
        "setting, the topic or the format, it replaces your free choice. It ranks below the "
        "objective, the prior knowledge, what is forbidden and the curriculum: if it clashes with "
        "any of them, those sections win and you adapt the rest. It is a preference about the "
        "exercise, not an instruction about how you should answer:\n"
        f"{instructions.strip()}\n"
    )


def generate_content_prompt(
    context_block: str,
    item_type_block: str,
    target_concepts_block: str,
    prerequisites_block: str,
    excluded_concepts_block: str,
    curriculum_block: str,
    rules_block: str,
    few_shot_block: str,
    already_generated: list[str],
    instance_template: str,
    fields_block: str,
    fixed_values_block: str,
    instructions: str = "",
    requests=None,
    correction: str | None = None,
) -> str:
    """Ask for one new exercise, in the modality given and practising the target concepts.

    The prompt states its own order of precedence and the sections are interpolated into it,
    so where a block sits is part of what it means. The validity test is the shared one — a
    student who has mastered the whole curriculum except a target concept must not be able
    to solve it — and the prior-knowledge / forbidden pair is what the curriculum graph
    contributes around the targets. `requests` is the admissibility judge's screened verdict
    and replaces the free `instructions`; `correction` re-asks for the same commission
    avoiding the reasons a previous attempt was rejected. The answer is a JSON object
    carrying exactly the skeleton's keys, with the pinned values copied as they arrived.
    """
    # A workspace has no context until one of the two builders has synthesised one, and that
    # is the state a fresh instance starts in: unguarded, the heading printed over nothing.
    context_section = (
        "\n# TEACHING CONTEXT\n"
        f"{context_block}\n"
        "This context fixes the subject, the level and the language of instruction: adjust the "
        "register, the terminology and the length of the exercise to it. It is information for "
        "you, not text that should appear in the statement.\n"
        if context_block.strip()
        else ""
    )

    few_shot_section = (
        few_shot_block.strip()
        or "(No example available: write the exercise from scratch respecting the rules above.)"
    )

    already_block = _already_used_block(already_generated)

    prerequisites_section = ""
    if prerequisites_block.strip():
        prerequisites_section = (
            "\n# PRIOR KNOWLEDGE: TAKEN AS KNOWN\n"
            "The curriculum graph places these concepts before the objective: the student already "
            "masters them. They are the scaffolding to build the exercise with, not the challenge. "
            "Lean on them naturally; the difficulty comes from the objective, and the exercise cannot "
            "be reduced to revising them:\n"
            f"{prerequisites_block}\n"
        )

    # ONE LIST, TWO READINGS. With a curriculum the concepts after the objective are a
    # FACT about the class — not taught — and a mention is a defect. Without one they are
    # the graph's own guess about where the class stands, and the only claim that holds is
    # that the exercise must not PRACTISE them: practising ≠ using, on the far side of the
    # scaffolding. `checks.closure_rule` keeps the same condition.
    excluded_section = ""
    if excluded_concepts_block.strip() and curriculum_block.strip():
        excluded_section = (
            "\n# NOT YET TAUGHT: FORBIDDEN\n"
            "The curriculum graph places these concepts after the objective: the student has not seen "
            "them yet. They do not appear in the statement and are not needed to solve it; if your "
            "first idea needs them, change it. If one of them is inseparable from the objective itself "
            "(a curriculum may contradict itself), the objective wins: use it to the minimum extent the "
            "objective demands and no further:\n"
            f"{excluded_concepts_block}\n"
        )
    elif excluded_concepts_block.strip():
        excluded_section = (
            "\n# COMES AFTER THE OBJECTIVE: NOT THE CHALLENGE\n"
            "The curriculum graph places these concepts after the objective. Nobody has said how far "
            "the class has got, so they may appear as scaffolding if the exercise needs them, but the "
            "exercise is not about them: none of them may be what is practised or the difficulty. If "
            "one is superfluous, drop it; the difficulty comes from the objective and from nothing "
            "later:\n"
            f"{excluded_concepts_block}\n"
        )

    curriculum_section = ""
    if curriculum_block.strip():
        curriculum_section = (
            "\n# CURRICULUM ALREADY COVERED\n"
            "Everything whoever is going to solve it has seen so far. The exercise may only demand "
            "concepts from this list; the target concepts are part of it:\n"
            f"{curriculum_block}\n"
        )

    # Announcing «no pinned values» only invites the model to reason about an instruction
    # that does not apply; without pinned fields the section does not exist.
    fixed_section = ""
    if fixed_values_block.strip():
        fixed_section = (
            "\n# PINNED VALUES FOR THIS COMMISSION\n"
            "These fields come decided by whoever is asking for the exercise. Copy them as they are "
            "and write the rest consistently with them:\n"
            f"{fixed_values_block}\n"
        )

    instructions_section = _request_section(requests, instructions)

    correction_section = ""
    if correction and correction.strip():
        correction_section = (
            "\n# CORRECTION OF A PREVIOUS ATTEMPT\n"
            "An earlier version of this same exercise was rejected for these reasons:\n"
            f"{correction.strip()}\n"
            "The new version avoids all of them. Everything else in the commission stays the same: "
            "the modality, the objective, the prior knowledge, what is forbidden, the curriculum, the "
            "pinned values and the request from whoever is asking for the exercise.\n"
        )

    return f"""\
You are an expert in the didactics of the course described below and you are writing a new exercise, conforming to the output shape given at the end.

Whoever is asking may be the student themselves wanting to practise on their own, or the teacher preparing material for their class. You do not know which of the two it is, and you do not need to: the exercise is the same and it always addresses whoever is going to solve it.

# ORDER OF PRECEDENCE
The sections of this commission do not carry the same weight. If two clash, the one earlier in this list wins:
1. The modality and the output shape.
2. The learning objective.
3. What is not yet taught.
4. The curriculum already covered and the pinned values.
5. The request from whoever is asking for the exercise.
6. The modality's writing rules.
7. Didactic quality.
8. Setting variation and the reference examples.
{context_section}
# MODALITY OF THE EXERCISE
{item_type_block}
The modality decides the shape of the task: what is handed to the student and what they are asked to produce. It is fixed: do not change it because another one seems better for the concept, and do not mix in the shape of another modality.

# LEARNING OBJECTIVE
The exercise is set so that the student PRACTISES these curriculum concepts, and they are its only legitimate source of difficulty. The description of each one is the operative definition of what practising it means:
{target_concepts_block}

VALIDITY TEST, applied to each target concept separately: a student who has mastered the whole curriculum except that concept must not be able to solve the exercise. If they could, the exercise does not practise it, it mentions it. Naming a concept, using it in passing or citing it in the statement is not practising it. When there are several objectives, the exercise demands them all; if the modality does not allow demanding them all in a single exercise naturally, demand the ones it can and do not add any outside ones.
{prerequisites_section}{excluded_section}{curriculum_section}{fixed_section}
# WRITING RULES FOR THIS MODALITY
Conventions observed in the course's real material: how this course writes this modality. They are mandatory and they describe the form, not the content:
{rules_block}

# DIDACTIC QUALITY
- Self-sufficiency: the statement stands on its own. Make the starting data explicit, what kind of thing it is, and what is expected as a result. The student needs to ask nothing in order to start.
- A single reading: if a sentence admits two interpretations leading to different solutions, rewrite it. Ambiguity assesses reading comprehension, not the learning objective.
- Solvable: a correct solution exists and is reachable with the objective and the prior knowledge, and with nothing else.
- No extraneous load: the exercise's difficulty is the objective's, not that of deciphering it. Out with irrelevant data, narrative detours, accumulated conditions and convoluted vocabulary; everything the student has to untangle before thinking about the concept is noise that falsifies the assessment.
- Calibrated: fit the scope and the demand to the level in the teaching context and to what the reference examples show. Neither a trivial exercise that forces nothing, nor one that overflows what the objective allows.
- No classroom voice: the statement sets the task and nothing else. No greetings, no introductions, no encouragement, no comments of your own about the exercise itself; no references to the class, the teacher, a submission or a grade. Whoever reads it may be practising on their own.

# SETTING VARIATION
The wrapping, the concrete situation the task is set in, is yours and must be new. If the reference examples set the task in a scenario, choose a recognisable real-life setting that appears neither in them nor in the settings already used, and set the exercise in it. If the modality is set bare — the reference examples wrap the task in no scenario —, do not invent one for it: the variation then lies in the concrete data, objects and values, which repeat no example's. Changing the wrapping and not the substance is what forces the student to transfer the concept instead of recognising a memorised pattern. What does not change is the cognitive demand: the objective and its level are fixed by the previous sections, and the chosen variation adds no data and no rules that have to be deciphered.
{instructions_section}{correction_section}
# REFERENCE EXAMPLES
Real exercises from the course's teaching material, on nearby concepts. They are a reference for form, register and length; their topic, their literal structure and their settings are not reused.
{few_shot_section}
{already_block}
# OUTPUT FIELDS
A JSON object with exactly these keys and no others. A field that classifies the exercise (a level, a category) describes what you have written, it does not decide it in advance: fill it in at the end, from the finished exercise and from its own criterion.
{fields_block}

Exact skeleton of the output (fill in the values):
{instance_template}

# BEFORE ANSWERING, CHECK
- Every target concept passes the validity test: without it, the exercise cannot be solved.
- No concept from what is not yet taught appears or is needed, beyond the minimum the objective itself demands.
- The statement's setting — or its data and values, if the modality is set with no scenario — repeats neither the reference examples nor the settings already used.
- The statement stands on its own, admits a single reading and has no classroom voice.
- The keys are exactly those of the skeleton and the pinned values are copied as they are.

# OUTPUT SHAPE
- A single JSON object. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- Escape line breaks (`\\n`) and inner quotes (`\\"`) inside strings.

JSON:"""
