"""The synthesis of the subject's context, called by BOTH builders at the end of a build.

The graph contributes the names of its syllabus blocks and the profile its modalities, and
neither sees what the other knows, so the call is always a MERGE: what is already written
goes in and a text incorporating it comes out. Preservation is what the prompt legislates
hardest, because a model handed a text and new material rewrites the text, and repeated on
every rebuild that paraphrases a person's words until they stop being theirs.
"""


def synthesize_content_context_prompt(
    current_block: str,
    evidence_block: str,
    source_label: str,
    max_chars: int,
) -> str:
    """Ask for the subject in prose, merging in whatever context is already written.

    The answer is `narrative` plus the three facts another part of the system needs
    separately — `subject`, `educational_level` and `language_of_instruction`, each an empty
    string when it cannot be inferred safely and each consistent with the prose.
    `source_label` names whose evidence is being folded in; `max_chars` is a hard ceiling,
    because this text is paid for on every call the system makes.
    """
    current_section = (
        "\n# CONTEXT THAT ALREADY EXISTS — A STARTING POINT, NOT A DRAFT TO REWRITE\n"
        f"{current_block}\n"
        if current_block.strip()
        else "\n# CONTEXT THAT ALREADY EXISTS\n(None yet: you are writing it for the first time.)\n"
    )
    return f"""\
Write, in prose, WHAT SUBJECT THIS IS. The text you produce is interpolated into every prompt of a system that generates learning material: it is what fixes the subject, the level of demand, the language and the conventions particular to this subject for everything that system writes afterwards.

You are not describing a syllabus or a course programme. You are describing the TERRAIN: what this is about, who it addresses, what language it is taught in and what conventions make it recognisable.
{current_section}
# WHAT {source_label} CONTRIBUTES
{evidence_block}

# HOW TO MERGE
- WHAT WAS ALREADY THERE IS KEPT. Every statement in the existing context survives into the final text, and if it can survive in its own words, it survives in its own words. A person may have written it by hand; paraphrasing it without need is losing it a little at a time.
- YOU ONLY ADD WHAT THE NEW MATERIAL GENUINELY CONTRIBUTES. If it contributes nothing that was not already said, return the context that was already there, unchanged. That is a correct and frequent answer.
- IF THEY CONTRADICT EACH OTHER, WHAT WAS ALREADY THERE WINS. The new material is a partial view of the subject; the existing context may come from somebody who knows the whole of it.
- DO NOT INVENT. No university, no academic year, no degree programme, no number of hours, no bibliography, nothing that is not in one of the two blocks above. When in doubt, leave it out.

# WHAT THE TEXT MUST BE LIKE
- CONTINUOUS PROSE, in the subject's language of instruction. One or two sentences running on; no lists, no bullets, no headings, no key-value pairs.
- AT MOST {max_chars} CHARACTERS. It is a hard ceiling, and it exists because this text is paid for on every call the system makes.
- NO ENUMERATED SYLLABUS. You may say in one sentence where the subject goes («it covers everything from the elementary notions to the advanced techniques at the end of the course»); you may not list the concepts or copy the names of the blocks one by one. The graph is there for that, and whoever reads this has it in front of them.
- NO METACOMMENTARY. Do not talk about the system, or about this task, or about what you did to write it. The text starts by describing the subject.
- NO ADDRESSEE. Do not address anybody: no «you», no «the student must», no «bear in mind that». It is a description, not an instruction.

# THE THREE FACTS, SEPARATELY
Besides the prose, extract three loose facts, because another part of the system needs them separately and cannot read the paragraph:
- `subject`: the name of the subject or course.
- `educational_level`: the stage or year («first year of an undergraduate degree», «upper secondary»).
- `language_of_instruction`: the language it is taught in.
Each one an empty string if it cannot be inferred safely from the blocks above. They must be CONSISTENT with the prose: whatever they say has to be said in it too.

# OUTPUT RULES
- A single JSON object with exactly the keys `narrative`, `subject`, `educational_level` and `language_of_instruction`. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- `narrative` on ONE SINGLE LINE: escape line breaks (`\\n`) and inner quotes (`\\"`).

JSON:"""
