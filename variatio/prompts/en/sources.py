"""Reading the raw documents: a page transcribed, a seam decided, a fragment made items."""

from ..marks import CORRECT_ANSWER_MARK, EMPTY_IMAGE_MARK, EMPTY_PAGE_MARK, SEAM_SEPARATORS

__all__ = [
    "CORRECT_ANSWER_MARK",
    "EMPTY_IMAGE_MARK",
    "EMPTY_PAGE_MARK",
    "IMAGE_RULES",
    "SEAM_SEPARATORS",
    "format_content_prompt",
    "merge_pages_prompt",
    "transcribe_image_prompt",
    "transcribe_page_prompt",
]

# ONE block for the two prompts that meet an image: the page prompt, where the image is a
# figure on the page, and the image prompt, where it arrives alone out of a Word or
# PowerPoint file. An image is transcribed by what it CONTAINS and described only when
# nothing can be copied — a description of a formula cannot be solved from, and a
# description of a screenshot destroys the "write a program that prints this" exercise
# whose expected output was the screenshot.
IMAGE_RULES = """\
# IMAGES AND FIGURES
An image is transcribed by what it CONTAINS, and described only when there is nothing to copy:
- A formula or mathematical expression typeset as an image is transcribed in LaTeX, symbol by symbol — `$…$` inline, `$$…$$` on its own.
- A screenshot of code, of a terminal or of a program's output is transcribed as a ``` block with its exact line breaks and indentation. Only the content counts: leave out everything that belongs to the application and not to the document (menus, toolbars, ruler, tabs, the editor's line numbers, window borders, taskbar).
- A table is transcribed as a Markdown table, cell by cell.
- Text (a scanned statement, a note, a label) is transcribed as text.
- Only what cannot be copied as text — a diagram, a plot, a schematic, a photograph — is noted in its place as `[figure: what it shows]`, in one sentence. Say what is SEEN (the axes and magnitudes of a plot, the components of a schematic, the labels it carries) without reading values that cannot be read clearly or interpreting what it means. The note never replaces the text accompanying the figure, which is transcribed like everything else.
- The same fidelity rules hold inside an image: copy character by character, do not solve, do not complete, do not correct, and `[illegible]` marks what cannot be read."""


def transcribe_page_prompt(page_number: int, page_count: int) -> str:
    """Ask for one page image copied into Markdown, character by character.

    The whole route stands on "copy, do not interpret": a later extractor reads the
    transcription believing it is the original document, so anything changed becomes false
    teaching material. The only mark the model may add is `CORRECT_ANSWER_MARK`, on a
    visually highlighted answer option; a page carrying nothing but logos and page numbers
    comes back as `EMPTY_PAGE_MARK`, which `pages.py` matches. The answer is bare Markdown.
    A figure on the page follows `IMAGE_RULES`, the same block the standalone image prompt
    carries, so an image is read the same way whichever route brought it.
    """
    return f"""\
Transcribe into Markdown PAGE {page_number} of {page_count} of a teaching-material document. You have it in front of you as an image.

Your job is to COPY what is on the page, not to interpret it. A later extractor will read your transcription believing it is the original document, so anything you change becomes false teaching material.

# READING ORDER
Transcribe in the order a person would read it. Each statement must stay next to the code, table, image or options that belong to it, in the place where they appear. If the page has columns, follow a whole column before moving to the next.

# STRUCTURE
The page's titles and headings are marked with `#` following the original's visual hierarchy (size, bold, numbering): `#` for the title of a unit, topic or chapter — the large line it opens with, such as «Unit 2 – Modularity» or «Chapter 3. Recursion» —, `##` for a section and `###` for a subsection. A heading is a line on its own that titles what comes under it; a sentence of the text, a label inside an exercise, the statement of a question or an answer option are NOT headings. The later extractor locates each unit through these headings, so a title transcribed as a loose line vanishes from the corpus's index.

# FIDELITY — THE MOST IMPORTANT PART
- Copy CHARACTER BY CHARACTER. `a -= 1` is not `a = a - 1`. `x = x - 1` is not `x = x + 1`. `range (0,8)` keeps its space. Do not normalise, do not modernise, do not fix the style.
- Do NOT solve anything, do NOT complete what is missing, do NOT correct errors in the document. If the code has a bug, the bug is part of the exercise and is transcribed as it is.
- Respect the original's spelling and accents.
- If something is illegible, write `[illegible]` in its place. Never guess.

# CODE
Code goes in blocks delimited by ``` keeping its line breaks and indentation EXACTLY. It is what survives a careless transcription worst and what does the most damage: a code fragment with flattened indentation or a changed operator stops being the exercise it was.

# MATHEMATICAL NOTATION
Formulas and mathematical expressions are copied with their notation, symbol by symbol and unit by unit. If the original typesets them (fractions, subscripts, integrals, vectors), transcribe them in LaTeX — `$…$` inline, `$$…$$` on their own — and use that same convention through the WHOLE document. If the original writes them in plain text, leave them in plain text. Do not solve, do not simplify, do not swap the notation for an equivalent one.

{IMAGE_RULES}

# MARKED ANSWERS
If one answer option is visually highlighted with respect to the others — a different colour, bold, underline, a box, a mark in the margin — add ` {CORRECT_ANSWER_MARK}` at the end of that line and nothing else. It is the only mark you may add to the text. If none is highlighted, mark none: do not deduce which one is correct.

# WHAT TO LEAVE OUT
Logos, crests, institutional headers and footers, page numbers and watermarks. Everything else is transcribed, including tables (in Markdown) and administrative statements that form part of an exercise.

# CONTINUITY
Transcribe only what you see on THIS page. If an exercise starts here and continues on the next one, cut where the page cuts: do not complete it and do not write notes about it.

# OUTPUT
Only the page's Markdown. No preamble, no comments of your own, no ```markdown wrapping the whole, no saying «Here is the transcription». If the page contains nothing but omittable elements, answer exactly `{EMPTY_PAGE_MARK}`.

Markdown:"""


def transcribe_image_prompt(image_number: int, image_count: int) -> str:
    """Ask for one image of a Word or PowerPoint document copied into Markdown.

    The image reaches the model alone — Docling keeps the text around it — and what comes
    back is spliced into the document exactly where the image was, so the answer has to be
    the content itself in the form the surrounding Markdown would give it: LaTeX for a
    formula, a fence for a screenshot of code, a table for a table, `[figure: …]` only for
    what cannot be copied. A logo, a crest or an ornament comes back as `EMPTY_IMAGE_MARK`,
    which `pages.py` matches and drops.
    """
    return f"""\
Transcribe into Markdown IMAGE {image_number} of {image_count} of a teaching-material document (a Word or PowerPoint file). You have it in front of you; you do not see the text around it.

Your job is to COPY what is in the image, not to interpret it. What you return will be inserted into the document in the exact place the image occupied, and a later extractor will read it believing it is the original document, so anything you change becomes false teaching material.

{IMAGE_RULES}

# MARKED ANSWERS
If the image contains answer options and one is visually highlighted with respect to the others — a different colour, bold, underline, a box, a mark in the margin — add ` {CORRECT_ANSWER_MARK}` at the end of that line and nothing else. It is the only mark you may add. If none is highlighted, mark none.

# WHAT NOT TO TRANSCRIBE
A logo, a crest, an ornament, a decorative rule, an icon or a photograph with no teaching content: answer exactly `{EMPTY_IMAGE_MARK}` and nothing else.

# OUTPUT
Only the Markdown that replaces the image. No preamble, no comments of your own, no ```markdown wrapping the whole, no saying «Here is the transcription». If the image has nothing to transcribe, answer exactly `{EMPTY_IMAGE_MARK}`.

Markdown:"""


def merge_pages_prompt(tail: str, head: str, page_number: int, page_count: int) -> str:
    """Ask how two consecutively transcribed pages join, and nothing else.

    The certain seams are decided deterministically before the call; only the ambiguous ones
    reach here. The answer is `continues`, a `separator` out of `SEAM_SEPARATORS`,
    `drop_head_lines` (0 when in doubt — dropping a line of content loses teaching material
    and leaving a repeated header does not) and a short `reason`. The model classifies and
    never rewrites: one word of its own in the document would be false teaching material.
    """
    return f"""\
Two consecutive pages of a teaching document were transcribed separately. Decide HOW THEY JOIN, and nothing else.

You do not write text: you do not complete, you do not correct, you do not rewrite, you do not summarise, you do not translate. Another process has already copied character by character what was on each page, and your only output is a separator and a number. Any word of yours ending up in the document would be false teaching material.

# END OF PAGE {page_number - 1} OF {page_count}
<<<TAIL>>>
{tail}
<<<END OF TAIL>>>

# START OF PAGE {page_number} OF {page_count}
<<<HEAD>>>
{head}
<<<END OF HEAD>>>

# WHAT TO DECIDE
1. `continues`: true if what opens the second page continues what the first left half-finished — a cut sentence, a split code block, a table that goes on, a list that goes on, a split word. false if the second page starts something new.
2. `separator`: what goes between the two transcriptions.
   - `none`: nothing. Only when the first cuts a word or an identifier in half.
   - `space`: one space. A sentence that continues on the next page.
   - `newline`: a line break. A code block, a table or a list that continue: a blank line would break the structure.
   - `paragraph`: a blank line. The normal case, when the second page starts something new.
3. `drop_head_lines`: how many lines from the start of the HEAD have to be discarded for being mechanical repetition of the layout rather than content — a repeated page header, a footer, the number of the same exercise the tail already carried. 0 almost always. When in doubt, 0: discarding a line of content loses teaching material and leaving a repeated header does not.
4. `reason`: a short sentence in English saying why.

# OUTPUT
A single JSON object: {{"continues": true|false, "separator": "none"|"space"|"newline"|"paragraph", "drop_head_lines": 0, "reason": "..."}}
Nothing before, nothing after, no ```json.

JSON:"""


def format_content_prompt(
    content: str,
    types_block: str,
    context_block: str = "",
    type_keys: list[str] | None = None,
) -> str:
    """Ask for the learning items of one markdown fragment, each under one modality's schema.

    Classify first, extract afterwards: every object carries `item_type` — one of
    `type_keys` — plus that modality's own fields and no other's. Values are copied
    verbatim, a field the source does not carry goes to `null` rather than being invented,
    and `CORRECT_ANSWER_MARK` is read for the correct option and then stripped out of the
    value. A fragment that sets no task comes back as `[]`; the answer is a JSON array.
    """
    context_section = (
        f"\n# TEACHING CONTEXT OF THE DOCUMENT\n{context_block}\n" if context_block.strip() else ""
    )

    keys = ", ".join(f"`{k}`" for k in (type_keys or []))

    return f"""\
Extract the LEARNING ITEMS from a pre-segmented markdown fragment of teaching material.

A learning item is any unit the material SETS THE STUDENT AS A TASK: an exercise, a problem, an activity, a question, a case study. Coming with its solution attached does not disqualify it — it is still an item, with its solution included.

These are NOT learning items and must not be extracted: the theoretical exposition of the syllabus, explanations and definitions, the examples the text uses to ILLUSTRATE an explanation without asking anything of the student, tables of contents, unit objectives, rubrics, bibliography and administrative notices. If the fragment sets no task, return `[]`.

The input contains one or several items. If there are several, they come separated by `---` lines. Each block between separators (or the whole input if it is a single block) represents exactly ONE item. Within a block, everything you find — sub-questions, parts (a/b/c, i/ii/iii), embedded code blocks, follow-up instructions, explanatory paragraphs, tables, examples — belongs to that single item: the parts are a progression of the same task, not separate tasks.

# CLASSIFY FIRST, EXTRACT AFTERWARDS
The course sets its tasks in several MODALITIES, and each one has its own field schema. For EACH item: decide first which modality it belongs to, and extract afterwards using the schema OF THAT modality and no other.

Every object you return carries an `item_type` key with the key of its modality ({keys}), PLUS the fields declared by that modality. Without `item_type` the item is discarded.

Choose the modality by what the item ASKS OF THE STUDENT, not by its topic or its difficulty. If an item fits two, keep the one whose fields you can fill completely from what is in the text. If it fits none, do NOT extract it: it is better to lose an item than to invent an anatomy for it.

# MODALITIES AND THEIR SCHEMAS
{types_block}

# EXTRACTION RULES
- Copy the values literally from the source text. Do not rewrite, do not translate, do not summarise, do not invent content. What is extracted is real teaching material: altering it destroys exactly what makes it useful as an example.
- If a field admits null and the content does not appear in the source, set it to null. Never fabricate content to fill it in: a statement with no solution in the material is a legitimate item, one with an invented solution is false teaching material.
- Do not mix fields from two modalities in the same object: the only valid fields are those of the modality you declared in `item_type`.
- The material may come from a transcription that marks the correct option of a closed question with `{CORRECT_ANSWER_MARK}`. That mark is NOT part of the text: use it to know which answer is correct and remove it from the value you extract.
- Remove leading enumeration markers (`1.`, `2)`, `Exercise 3:`, `Ejercicio 4.`, `Problem 5 -`, `Part 6:`, `Section 7 –`, etc.) from the text fields. Values must start with the first real character of the content, not with a number or a label.
- For multiline strings (code, prose with paragraphs): escape line breaks as `\\n` and inner quotes as `\\"`.
- Non-ASCII characters — accents, «ñ», «→», «≤», typographic quotes — are written as themselves, as text, and NEVER as `\\uXXXX` escape sequences: a mis-escaped accent is not a formatting error, it is a letter lost from the material.
- Respect the schema's constraints (`minLength`, `maxLength`, `pattern`, etc.).

# OUTPUT RULES
- A single JSON array. Nothing before, nothing after.
- Each object carries `item_type` plus the fields of that modality.
- No ```json, no backticks, no comments.
- If the fragment sets the student no task, return `[]`.
{context_section}
<<<CONTENT>>>
{content}
<<<END>>>

JSON:"""
