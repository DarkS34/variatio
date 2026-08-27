def tag_concepts_prompt(
    statement: str,
    candidates: str,
    relations: str = "",
    context_block: str = "",
) -> str:
    context_section = f"\n# TEACHING CONTEXT\n{context_block}\n" if context_block.strip() else ""

    relations_block = ""
    if relations.strip():
        relations_block = (
            "\n# RELATIONS AMONG THE CANDIDATES\n"
            "Relations from the curriculum graph between the candidates themselves. They say how these concepts are ordered in the learning sequence; use them to choose the right LEVEL OF SPECIFICITY:\n"
            f"{relations}\n"
        )

    return f"""\
You are cataloguing the exercise bank of a course. For the exercise below, decide WHICH CURRICULUM CONCEPTS it makes whoever solves it practise.
{context_section}
# CANDIDATE CONCEPTS
Ordered from most to least semantically relevant to the statement. Under each name is the concept's description: it describes the task set for the student when they practise it. Judge by the description, not by the name.
{candidates}
{relations_block}
# THE CENTRAL DISTINCTION: PRACTISING IS NOT USING
Every exercise USES many concepts and PRACTISES a few. What is tagged here is what it PRACTISES.
- A concept is PRACTISED if the exercise tests what the student can do with it.
- A concept is USED when it appears as a vehicle, a support or a notation for the task, but is taken as already mastered and the exercise does not exercise it at all.
- THE DECIDING TEST, AND IT IS THE PRIMARY ONE'S: imagine a student who has mastered everything else except that concept. Would they solve the exercise anyway? If the answer is yes, that concept is not the exercise's OBJECTIVE.
- The two output fields are decided by DIFFERENT questions: the one above fixes `primary_concept`; `concepts` answers a broader one, described in the rules.

# OUTPUT SCHEMA
{{
  "concepts": ["Concept A", "Concept B"],
  "primary_concept": "Concept A"
}}

# RULES
- Use ONLY concepts from the candidate list. Do not invent or paraphrase names.
- ORDER OF DECISION: fix the primary FIRST, applying only the deciding test and without thinking about the list yet. Only then widen out to `concepts`. Widening the list cannot change the primary you already fixed.
- `primary_concept`: ONE ONLY, the exercise's LEARNING OBJECTIVE — what the exercise exists to test, what would be assessed with it. Here the deciding test applies without concessions. It must also appear in `concepts`.
- `concepts`: the primary PLUS every concept this exercise serves to practise, even if it is not its central objective. The question here is broader and it is this one: would a teacher looking for exercises to work on that concept be glad to find this one? If the answer is yes, it goes in the list.
- What still stays OUT of `concepts`: what the statement merely mentions, what it uses as pure notation and what it takes as known without exercising it at all. Broad is not indiscriminate.
- HOW MANY: two or three is normal, four the maximum. If you go past four you have let tools in.
- SPECIFICITY: between two candidates where one is a kind of the other, or a part of the other, the primary is the MOST SPECIFIC one the exercise genuinely practises. The general one may accompany it in `concepts`.
- LEARNING SEQUENCE: if one candidate is a prerequisite of another and both appear, the PRIMARY is normally the later one. The prerequisite goes in `concepts` if the exercise exercises it, not if it merely leans on it.
- The order of the candidates is a hint, not an answer: the first one need not be the primary.
- A single element in `concepts` only if the exercise genuinely practises nothing else.
- If NO candidate is what the exercise centrally practises, return {{"concepts": [], "primary_concept": null}}. Use this option with judgement: only when no candidate describes the exercise's real objective, not out of mere uncertainty.
- Answer ONLY with the JSON. No text before or after, no backticks, no comments.

# EXERCISE TO TAG
{statement}

JSON:"""
