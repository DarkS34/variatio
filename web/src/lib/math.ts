/**
 * Where a formula starts and stops, and — mostly — where it does not.
 *
 * The generator writes TeX because the corpus does: an item about automata comes back with
 * `$\Sigma = \{0, 1\}$` and `$\delta(q_0, 1) = q_1$` in its statement, and until this
 * existed the card showed the source. Splitting is a pure function so the rule can be
 * pinned by a test, which matters more here than in most places: `$` is not only a
 * delimiter in this corpus. The reference bank is full of LR parsing tables where it is the
 * END-OF-INPUT MARKER — `| a | b | e | x | y | $ | S | A |`, `Arcs: 8 --> $ --> Accept`,
 * `Siguiente (A): $+x` — and two of those on one line must never pair up into a formula
 * that swallows the row between them.
 *
 * Four conditions do that, and each one is paying for a real line above:
 * - the opening `$` is not glued to a word and is not itself escaped (`US$5`, `\$`);
 * - what follows it is not whitespace, so `| $ | S |` opens nothing;
 * - the partner is on the SAME line and is not preceded by whitespace, so `--> $ -->`
 *   closes nothing;
 * - no backtick inside, so a code span quoted mid-sentence cannot be eaten by a stray `$`
 *   in front of it;
 * - a pipe on the outside closes the door too: `|a|$|S|$|b|` is an unpadded table row of
 *   those same end-of-input cells, and it is the one shape that got past the other three.
 *   The cost is a formula in an unpadded cell (`|$x$|`), which no page in this corpus
 *   writes — every real table pads — and the gain is that the formula's own content stays
 *   unrestricted, so `$1(0|1)^*0$` and `$|x|$` both survive.
 *
 * `\$` inside a formula is a literal dollar and does not close it, which is what the
 * `\\[^\n]` branch is for.
 */

const INLINE_MATH = /(?<![\w$\\|])\$(?![\s$])((?:[^$\n`\\]|\\[^\n])+?)(?<![\s\\])\$(?![\w$|])/;

// Display maths opens its own block rather than being fished out of a paragraph: a
// `\begin{array}` of production rules has lines starting with `-`, with `\` and with `|`,
// every one of which would otherwise close the paragraph and start a list or a table.
export const DISPLAY_OPEN = /^\s{0,3}\$\$/;
const DISPLAY_CLOSE = /\$\$\s*$/;

export type MathToken = { kind: "text"; value: string } | { kind: "math"; tex: string };

export function splitInlineMath(text: string): MathToken[] {
  const out: MathToken[] = [];
  let rest = text;

  while (rest) {
    const match = INLINE_MATH.exec(rest);
    if (!match) break;
    if (match.index > 0) out.push({ kind: "text", value: rest.slice(0, match.index) });
    out.push({ kind: "math", tex: match[1] });
    rest = rest.slice(match.index + match[0].length);
  }

  if (rest) out.push({ kind: "text", value: rest });
  return out;
}

/**
 * The display formula that starts at `lines[index]`, and the line after it.
 *
 * One line (`$$E \to E + T$$`) and several are the same block. An unclosed `$$` runs to the
 * end of what it was given rather than falling back to prose: half a formula shown as text
 * is the state this whole module exists to remove, and the block ends where the field does.
 */
export function takeDisplayMath(
  lines: string[],
  index: number,
): { tex: string; next: number } {
  const opened = lines[index].replace(DISPLAY_OPEN, "");
  if (DISPLAY_CLOSE.test(opened)) {
    return { tex: opened.replace(DISPLAY_CLOSE, "").trim(), next: index + 1 };
  }

  const body = [opened];
  let at = index + 1;
  while (at < lines.length && !DISPLAY_CLOSE.test(lines[at])) {
    body.push(lines[at]);
    at += 1;
  }
  if (at < lines.length) body.push(lines[at].replace(DISPLAY_CLOSE, ""));
  return { tex: body.join("\n").trim(), next: Math.min(at + 1, lines.length) };
}
