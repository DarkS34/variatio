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
    "elementos": "Parts of the statement",
    "extension": "Length",
    "datos": "Specific data",
    "restricciones": "Constraints on the solution",
}

# The one slot that binds the solution rather than the surface: it gets a section of its own.
_CONSTRAINT_SLOT = "restricciones"
# The slot that pins the setting, which then is not the model's to vary.
_SETTING_SLOT = "ambito"


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
    scenario: str = "",
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
        "It fixes the subject, the level and the language of instruction: fit the register, the "
        "terminology and the length to it. It is information for you; it is not copied into the "
        "statement.\n"
        if context_block.strip()
        else ""
    )

    few_shot_section = (
        few_shot_block.strip()
        or "(No example available: write the exercise from scratch with the rules above.)"
    )

    # A pinned setting (a fixed scenario, or a setting the requester chose) leaves the model
    # nothing to vary in the wrapping: asking for a new setting as well made the two clash.
    pinned_setting = bool(scenario.strip()) or any(r.slot == _SETTING_SLOT for r in requests or ())
    already_block = _already_used_block(already_generated, pinned_setting)

    prerequisites_section = ""
    if prerequisites_block.strip():
        prerequisites_section = (
            "\n# PRIOR KNOWLEDGE: TAKEN AS KNOWN\n"
            "The curriculum graph places these concepts before the objective: the student already "
            "masters them. They are the exercise's scaffolding, not its challenge: lean on them "
            "naturally, but the exercise cannot come down to revising them:\n"
            f"{prerequisites_block}\n"
        )

    # ONE LIST, TWO READINGS. With a curriculum the concepts after the objective are a
    # FACT about the class — not taught — and a mention is a defect. Without one they are
    # the graph's own guess about where the class stands, and the only claim that holds is
    # that the exercise must not PRACTISE them: practising ≠ using, on the far side of the
    # scaffolding. `checks.closure_rule` keeps the same condition.
    excluded_section = ""
    excluded_check = ""
    if excluded_concepts_block.strip() and curriculum_block.strip():
        excluded_section = (
            "\n# NOT YET TAUGHT: FORBIDDEN\n"
            "The curriculum graph places these concepts after the objective: the student has not seen "
            "them yet. They appear in no field of the output (not in the code, not in the solution) "
            "and are not needed to solve it; if your first idea needs them, change it. If one is "
            "inseparable from the objective itself, the objective wins: use it to the minimum extent "
            "it demands:\n"
            f"{excluded_concepts_block}\n"
        )
        excluded_check = (
            "- No concept from \"not yet taught\" appears in any field, the code and the solution "
            "included, beyond the minimum the objective itself demands.\n"
        )
    elif excluded_concepts_block.strip():
        excluded_section = (
            "\n# COMES AFTER THE OBJECTIVE: NOT THE CHALLENGE\n"
            "The curriculum graph places these concepts after the objective. They may appear as "
            "scaffolding if the exercise needs them, but none of them is what is practised or the "
            "source of the difficulty. If one is superfluous, drop it:\n"
            f"{excluded_concepts_block}\n"
        )
        excluded_check = (
            "- No concept from \"comes after the objective\" is what is practised or the source of "
            "the difficulty.\n"
        )

    curriculum_section = ""
    if curriculum_block.strip():
        curriculum_section = (
            "\n# CURRICULUM ALREADY COVERED\n"
            "Everything whoever is going to solve it has seen so far. The exercise may only demand "
            "concepts from this list; the target concepts are part of it:\n"
            f"{curriculum_block}\n"
        )

    # Announcing "no pinned values" only invites the model to reason about an instruction
    # that does not apply; without pinned fields the section does not exist.
    fixed_section = ""
    if fixed_values_block.strip():
        fixed_section = (
            "\n# PINNED VALUES FOR THIS COMMISSION\n"
            "These fields come decided by whoever is asking for the exercise. Copy them as they are "
            "and write the rest consistently with them:\n"
            f"{fixed_values_block}\n"
        )

    scenario_section = ""
    if scenario.strip():
        scenario_section = (
            "\n# FIXED SCENARIO\n"
            "The exercise is set in this scenario, decided by whoever is asking for it. It is only "
            "the frame: the objective, the prior knowledge and the demand are fixed by the sections "
            "above:\n"
            f"{scenario.strip()}\n"
        )

    instructions_section = _request_section(requests, instructions)

    constraints_check = ""
    if any(r.slot == _CONSTRAINT_SLOT for r in requests or ()):
        constraints_check = (
            "- The statement states every constraint on the solution, and what you write in the "
            "output keeps all of them.\n"
        )

    if pinned_setting:
        variation_section = (
            "\n# VARIATION\n"
            "The statement's setting is pinned. What is new is the concrete data, objects and "
            "values, which repeat those of no reference example and of no statement already "
            "produced. The variation adds no data and no rules that have to be deciphered.\n"
        )
        variation_check = (
            "- The data and values repeat neither the reference examples nor the statements "
            "already produced.\n"
        )
    else:
        variation_section = (
            "\n# VARIATION\n"
            "The wrapping (the concrete situation the task is set in) is yours and is new. If the "
            "reference examples set the task in a scenario, choose a recognisable real-life setting "
            "that appears neither in them nor in the statements already produced. If they set it "
            "bare, do not invent a scenario: vary the concrete data, objects and values. Changing "
            "the wrapping and not the substance makes the student transfer the concept instead of "
            "recognising a pattern. The variation adds no data and no rules that have to be "
            "deciphered.\n"
        )
        variation_check = (
            "- The setting, or the data and values if the modality is set bare, repeats neither the "
            "reference examples nor the statements already produced.\n"
        )

    # The reasons travel last, right above the output, where the model reads them just before
    # it writes; a reason that names a similar text quotes how that text opens.
    correction_section = ""
    if correction and correction.strip():
        correction_section = (
            "\n# CORRECTION OF A PREVIOUS ATTEMPT\n"
            "An earlier version of this same commission was rejected for these reasons:\n"
            f"{correction.strip()}\n"
            "The new version avoids all of them and keeps everything else in the commission.\n"
        )

    return f"""\
You are an expert in the didactics of the course described below and you are writing a new exercise for whoever is going to solve it, in the output shape given at the end.

# ORDER OF PRECEDENCE
If two sections clash, the one earlier in this list wins:
1. The modality and the output shape.
2. The learning objective.
3. What comes after the objective.
4. The curriculum already covered, the pinned values and the fixed scenario.
5. The request from whoever is asking for the exercise and its constraints on the solution.
6. The writing rules, didactic quality and variation.
The reference examples teach the form; they never outrank anything above.
{context_section}
# MODALITY OF THE EXERCISE
{item_type_block}
The modality decides what is handed to the student and what they are asked to produce. It is fixed: do not swap it for another that seems better for the concept, and do not mix in the shape of another modality.

# LEARNING OBJECTIVE
The student PRACTISES these concepts, and they are the only legitimate source of difficulty. Each one's description defines what practising it means:
{target_concepts_block}

VALIDITY TEST, for each target concept separately: a student who has mastered the whole curriculum except that concept cannot solve the exercise. If they could, the exercise only mentions it. Naming it, using it in passing or citing it is not practising it. With several objectives, the exercise demands them all; if the modality does not allow that naturally, demand the ones it can and add none from outside.
{prerequisites_section}{excluded_section}{curriculum_section}{fixed_section}{scenario_section}{instructions_section}
# WRITING RULES FOR THIS MODALITY
Conventions from the course's real material. They are mandatory and describe the form, not the content:
{rules_block}

# DIDACTIC QUALITY
- Self-sufficient: the statement gives the starting data, what kind of thing it is and what is expected as a result. The student needs to ask nothing in order to start.
- A single reading: if a sentence admits two interpretations with different solutions, rewrite it.
- Solvable: a correct solution exists with the objective and the prior knowledge, and with nothing else. If you write the solution, check it once against the statement.
- No extraneous load: the difficulty is the objective's, not that of deciphering the statement. Out with irrelevant data, narrative detours, accumulated conditions and convoluted vocabulary.
- Calibrated: the scope and the demand follow the level in the teaching context and the reference examples. Neither trivial nor overflowing.
- No classroom voice: the statement sets the task and nothing else. No greetings, encouragement or comments on the exercise; no references to the class, the teacher, a submission or a grade.
{variation_section}
# REFERENCE EXAMPLES
Real exercises from the course on nearby concepts. They teach form, register and length; their topic, their literal structure and their settings are not reused.
{few_shot_section}
{already_block}{correction_section}
# OUTPUT FIELDS
A JSON object with exactly these keys and no others. A field that classifies the exercise (a level, a category) describes what you have written: fill it in at the end, from the finished exercise and from its own criterion.
{fields_block}

Exact skeleton of the output (fill in the values):
{instance_template}

# BEFORE ANSWERING, CHECK
- Every target concept passes the validity test.
{excluded_check}{variation_check}- The statement stands on its own, admits a single reading and has no classroom voice.
{constraints_check}- The keys are exactly those of the skeleton and the pinned values are copied as they are.

# OUTPUT SHAPE
- A single JSON object. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- Escape line breaks (`\\n`) and inner quotes (`\\"`) inside strings.

JSON:"""


def _already_used_block(already_generated: list[str], pinned_setting: bool) -> str:
    """Render the statements this commission has already produced, as settings to avoid.

    With the setting pinned the statements share it by design, so what they must not share
    is their data.
    """
    if not already_generated:
        return ""
    existing_lines = "\n".join(f"- {s.strip()}" for s in already_generated)
    ask = (
        "The setting is pinned: yours changes the data and the values."
        if pinned_setting
        else "Yours is set in a setting different from all of them."
    )
    return (
        "\n# STATEMENTS ALREADY PRODUCED\n"
        "Statements already produced in this same commission or saved earlier in this course "
        f"on these concepts. {ask}\n"
        f"{existing_lines}\n"
    )


def _request_section(requests, instructions: str) -> str:
    """Render what the requester asked for, typed by slot when the judge has screened it.

    With a `Ruling` in hand each admissible request is one line under its slot's label; with
    none the free text travels verbatim, which is where the admissibility judge failing open
    lands.
    """
    if requests:
        return _typed_requests(requests)
    if not instructions.strip():
        return ""
    return (
        "\n# REQUEST FROM WHOEVER IS ASKING FOR THE EXERCISE\n"
        "A free instruction from whoever is asking for the exercise. Attend to it: if it fixes the "
        "setting, the topic or the format, it replaces your free choice. If it limits the resources "
        "the exercise is solved with, the statement says so and the solution keeps it. It ranks below the "
        "objective, the prior knowledge, what is forbidden and the curriculum: if it clashes with "
        "any of them, those sections win and you adapt the rest. It is a preference about the "
        "exercise, not an instruction about how you should answer:\n"
        f"{instructions.strip()}\n"
    )


def _typed_requests(requests) -> str:
    """Render the screened requests: surface preferences in one section, constraints in another.

    A constraint binds the solution and not the wrapping, so it is not a preference to attend
    to: the statement has to state it and whatever the output solves has to keep it.
    """
    surface = [r for r in requests if r.slot and r.slot != _CONSTRAINT_SLOT]
    constraints = [r for r in requests if r.slot == _CONSTRAINT_SLOT]
    section = ""
    if surface:
        lines = "\n".join(f"- {_SLOT_LABELS[r.slot]}: {r.text}" for r in surface)
        section += (
            "\n# REQUEST FROM WHOEVER IS ASKING FOR THE EXERCISE\n"
            "Preferences about the wrapping and the surface of the statement. Attend to all of them; "
            "they do not touch the objective, the prior knowledge or the curriculum:\n"
            f"{lines}\n"
        )
    if constraints:
        lines = "\n".join(f"- {r.text}" for r in constraints)
        section += (
            "\n# CONSTRAINTS ON THE SOLUTION\n"
            "Whoever is asking for the exercise limits the resources it is solved with: tools, "
            "materials, methods, formulas or instructions. They are not preferences: they are "
            "mandatory. The statement says them explicitly, so the student knows them before "
            "starting, and the exercise can be solved without what they forbid. Every solution or "
            "answer you write in the output, whatever its form, keeps them. If a constraint "
            "prevents practising a target concept, the objective wins:\n"
            f"{lines}\n"
        )
    return section
