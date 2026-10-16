/**
 * A TUTOR'S REPLY, CUT WHERE ITS CLOSING QUESTIONS BEGIN.
 *
 * Every reply ends by asking — the method requires it — and the question is the part the
 * student has to answer, so the screen sets it apart from the explanation that leads to it.
 * Nothing marks it in the text, and nothing should: the reply is the model's prose, and a
 * marker asked of the model is one more thing it can get wrong. The cut is read off the
 * prose instead, from its end backwards:
 *
 * - the trailing blocks that end in a question mark are the questions;
 * - the first of them, when it is a plain paragraph, is cut again by sentence, so the lead-in
 *   it opens with («Piensa en el ejemplo del factorial.») stays with the explanation.
 *
 * It only ever cuts BETWEEN sentences and never inside inline code, a formula or an emphasis,
 * so both halves are still the Markdown they were. A question in the middle of a reply is
 * explanation: only what the reply closes with is what it asks.
 */
export interface ReplyParts {
  body: string;
  questions: string;
}

// What may close a sentence after its last mark: quotes (straight, angled and curly, written
// as escapes so the catalogue check does not read them as interface text), brackets and
// Markdown's emphasis.
const CLOSERS = "\"'\u00bb\u201d\u2019)]*_";
const ENDS = ".!?…";
// A block that is not a paragraph: a list, a quote, a heading, a table or a fence.
const NOT_PROSE = /^\s*(?:[-*+]\s|\d+[.)]\s|>|#|\||```|~~~)/;

export function splitReply(text: string): ReplyParts {
  const blocks = blocksOf(text);
  let first = blocks.length;
  while (first > 0 && asks(blocks[first - 1])) first -= 1;
  if (first === blocks.length) return { body: text.trim(), questions: "" };

  const body = blocks.slice(0, first);
  const questions = blocks.slice(first);
  const [lead, asked] = cutLead(questions[0]);
  if (lead) {
    body.push(lead);
    questions[0] = asked;
  }
  return { body: body.join("\n\n"), questions: questions.join("\n\n") };
}

/** The blocks blank lines separate, a fenced block kept whole whatever it holds. */
function blocksOf(text: string): string[] {
  const blocks: string[] = [];
  let current: string[] = [];
  let fenced = false;
  for (const line of text.split("\n")) {
    if (/^\s*(?:```|~~~)/.test(line)) fenced = !fenced;
    if (!fenced && line.trim() === "") {
      if (current.length) blocks.push(current.join("\n"));
      current = [];
    } else {
      current.push(line);
    }
  }
  if (current.length) blocks.push(current.join("\n"));
  return blocks;
}

function asks(block: string): boolean {
  let end = block.trimEnd().length;
  while (end > 0 && CLOSERS.includes(block[end - 1])) end -= 1;
  return block[end - 1] === "?";
}

/**
 * Cut a paragraph that ends asking into what leads in and what asks.
 *
 * A sentence ends at a mark followed by a space and by anything but a lowercase letter
 * («p. ej.» is no end), outside inline code and formulas. The cut is refused when it would
 * leave an emphasis open on one side.
 */
function cutLead(paragraph: string): [string, string] {
  if (NOT_PROSE.test(paragraph)) return ["", paragraph];
  const starts = [0];
  let code = false;
  let maths = false;
  for (let i = 0; i < paragraph.length; i += 1) {
    const char = paragraph[i];
    if (char === "`") code = !code;
    else if (char === "$" && !code) maths = !maths;
    if (code || maths || !ENDS.includes(char)) continue;
    let end = i + 1;
    while (end < paragraph.length && CLOSERS.includes(paragraph[end])) end += 1;
    let next = end;
    while (next < paragraph.length && /\s/.test(paragraph[next])) next += 1;
    if (next > end && next < paragraph.length && !/\p{Ll}/u.test(paragraph[next])) {
      starts.push(next);
      i = next - 1;
    }
  }
  let from = starts.length - 1;
  while (from > 0 && asks(paragraph.slice(starts[from - 1], starts[from]))) from -= 1;
  const lead = paragraph.slice(0, starts[from]).trim();
  const balanced = (lead.split("**").length - 1) % 2 === 0;
  return lead && balanced ? [lead, paragraph.slice(starts[from]).trim()] : ["", paragraph];
}
