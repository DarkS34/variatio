def classify_instructions_prompt(
    instructions: str,
    catalog,
    owners,
    targets: list[str],
    context_block: str = "",
) -> str:
    context_section = ""
    if context_block.strip():
        context_section = f"\n# TEACHING CONTEXT\n{context_block}\n"

    slots = "\n".join(f"- {s.key}: {s.label}. For example, «{s.example}»" for s in catalog)

    owner_lines = []
    for owner in owners:
        terms = ", ".join(f"«{t}»" for t in owner.terms)
        owner_lines.append(f"- {owner.key} ({owner.label}) decides: {terms}")
    owners_block = "\n".join(owner_lines)

    targets_block = ", ".join(f"«{t}»" for t in targets) or "(none)"

    # The owners are derived per instance, so an example about a control that may not
    # exist teaches the model to attribute the request to the nearest owner it can see.
    if any(owner.key.startswith("field:") for owner in owners):
        difficulty_rule = (
            "- «make it very hard» fixes the level of demand, and above there IS a control "
            "that decides it: it invades that control."
        )
    else:
        difficulty_rule = (
            "- «make it very hard» fixes the level of demand, and above there is NO control "
            "that decides it: it invades nothing. Do not attribute it to whichever owner "
            "most resembles it."
        )

    return f"""\
You classify the request written by whoever is commissioning an exercise. You do not write the exercise and you do not judge it: you only say, for each thing it asks for, whether it is one of the things that may be asked here or one of the things already decided elsewhere.
{context_section}
# WHAT IS ASKED FOR HERE
Four slots. A request that fits into one of them is admissible:
{slots}

# WHAT IS ALREADY DECIDED ELSEWHERE
Each line is a control on the form and what that control decides. A request that invades one of them is NOT admissible, and you must say which one it invades and with which exact term from the list:
{owners_block}

# THE TARGET CONCEPTS OF THIS COMMISSION
{targets_block}
Asking for something about them is NOT invading anything: they are the subject of the exercise. It is only an invasion to ask that a concept NOT on this line be practised.

# THE TEST
An exercise USES many concepts and PRACTISES one or two. The question, for each request, is which of the two it is asking for.
- «make it about a shopping list» USES the word list as a real-life setting: that is the `ambito` slot, not an invasion, even if the syllabus had a concept called «List».
- «make it about a library that lends books» is a building with books: that is `ambito`.
- «with a sample input and output» asks the statement to show a worked case: that is the `elementos` slot, even if the name of a concept appears inside the sentence.
- «make it practise another concept too» — one from the syllabus that is not among the targets — asks for a concept to be PRACTISED: it invades `concepts`.
{difficulty_rule}
- «write it in Spanish» changes the language, which the subject fixes: it invades `context`.
A word in the text coinciding with the name of a concept is NOT an invasion: only asking for that concept to be PRACTISED is.
An owner can only be invaded if it is on the list above. If what is asked fits no slot and no listed owner decides it, leave `slot` and `owner` as `null`: it is not this screen's business, nor any other's.
When in doubt between a slot and an owner, the slot wins: refusing a legitimate request costs more than letting a doubtful one through.

# THE REQUEST TO CLASSIFY
«{instructions.strip()}»

# THE OUTPUT
A JSON object with the key `requests`: one entry per distinct thing asked for in the text. A text asking for two things gives two entries.
Each entry carries:
- `text`: the fragment of the original text it refers to, copied verbatim.
- `slot`: the slot key if it is admissible; `null` if not.
- `owner`: the key of the invaded owner if it is not; `null` if it is.
- `term`: the EXACT term from that owner's list, copied character by character; `null` if `slot` is not `null`.
Never fill in `slot` and `owner` at the same time. Never invent a term that is not in the owner's list.
Nothing before or after the object. No ```json, no comments."""
