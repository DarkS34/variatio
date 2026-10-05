/**
 * Reading the difficulty criterion a profile wrote, one rung at a time.
 *
 * The criterion is ONE string in the artifact and stays one, which is what keeps extraction,
 * `fixed=` and the admissibility owners working with no migration. A person picks the rung
 * of the exercise they are commissioning, so the text has to be readable BESIDE THE OPTION
 * IT DESCRIBES rather than as one paragraph.
 *
 * The prompt legislates the shape (`variatio/prompts/{es,en}/profile.py`) and this splits
 * it. Deliberately lenient — `'basico':`, `"basico":`, `"Básico":` and a bare `basico:` all
 * count — and deliberately all-or-nothing: a text it cannot take apart is handed back
 * WHOLE, since half a criterion under one option is worse than the paragraph.
 */

export interface Rung {
  level: string;
  text: string;
}

export interface Criterion {
  /** What comes before the first rung: the axis. Empty when the text opens on a rung. */
  lead: string;
  /** In the order the modality declares them, and only the ones actually found. */
  rungs: Rung[];
}

/** Accent- and case-folded, with an index back into the source for every character. */
function fold(text: string): { folded: string; at: number[] } {
  let folded = "";
  const at: number[] = [];
  for (let i = 0; i < text.length; i += 1) {
    const one = text[i].normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    for (const character of one) {
      folded += character;
      at.push(i);
    }
  }
  return { folded, at };
}

const OPENS = `[\\s"'«‹(\\[]`;
const CLOSES = `["'»›)\\]]?`;

function escape(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Where each rung's clause starts, or null when fewer than two of them are marked.
 *
 * Two and not one: a single hit means the text merely mentions a level in passing, and
 * splitting on it would file the whole criterion under that one rung.
 */
function marks(description: string, levels: string[]) {
  const { folded, at } = fold(description);
  const found: { level: string; from: number; body: number }[] = [];
  for (const level of levels) {
    const needle = fold(level).folded;
    if (!needle) continue;
    const pattern = new RegExp(`(^|${OPENS})${escape(needle)}${CLOSES}\\s*:`, "u");
    const hit = pattern.exec(folded);
    if (!hit) continue;
    // The opening delimiter is part of the match but not of the mark: `at` maps the level's
    // own first character, so a leading space or quote stays with the clause before it.
    const start = hit.index + hit[1].length;
    found.push({ level, from: at[start], body: at[hit.index + hit[0].length - 1] + 1 });
  }
  return found.length >= 2 ? found.sort((a, b) => a.from - b.from) : null;
}

/**
 * What a clause inherits from the mark that follows it: the joining punctuation, and the
 * OPENING delimiter of the next rung — `from` points at the rung's own first letter, so
 * without this the axis ends "Grado de exigencia del ejercicio. '".
 */
const TRAILING = /[\s.,;:·—–\-"'«‹(\[]+$/u;

export function splitCriterion(
  description: string | null | undefined,
  levels: readonly string[],
): Criterion {
  const text = (description ?? "").trim();
  if (!text) return { lead: "", rungs: [] };

  const found = marks(text, [...levels]);
  if (!found) return { lead: text, rungs: [] };

  const byLevel = new Map<string, string>();
  found.forEach((mark, index) => {
    const end = index + 1 < found.length ? found[index + 1].from : text.length;
    byLevel.set(mark.level, text.slice(mark.body, end).trim().replace(TRAILING, ""));
  });

  return {
    lead: text.slice(0, found[0].from).trim().replace(TRAILING, ""),
    // The LADDER's order and not the text's: what a screen draws is the scale, and a
    // criterion that happened to name "avanzado" first must not reorder the options. A rung
    // that is opened and left empty says nothing, so it is not one of the rungs found.
    rungs: levels.filter((level) => byLevel.get(level)).map((level) => ({
      level,
      text: byLevel.get(level)!,
    })),
  };
}

const CLOSED = /[.!?…:;]$/u;

/** A clause as it is written into the criterion: trimmed, and closed by a full stop. */
function sentence(text: string): string {
  const value = text.trim();
  return !value || CLOSED.test(value) ? value : `${value}.`;
}

/**
 * The criterion written back as ONE string, in the shape the prompt legislates.
 *
 * It is what lets step 2 correct the criterion one rung at a time while the artifact keeps
 * its single `description`: the axis, then every rung opened by its value between « » and a
 * colon. EVERY rung is opened as soon as one is written, an empty one included —
 * `splitCriterion` needs two marks, and a criterion with one rung filled in would come back
 * whole, under the axis, the next time it is read. With no rung written the axis goes alone.
 */
export function joinCriterion(
  lead: string,
  clauses: Readonly<Record<string, string>>,
  levels: readonly string[],
): string {
  const written = levels.some((level) => (clauses[level] ?? "").trim());
  // The « » and the colon are the artifact's own marks, in whatever language the screen is.
  const open = (level: string) => `«${level}»: ${sentence(clauses[level] ?? "")}`; // i18n-exempt
  const rungs = written ? levels.map((level) => open(level).trim()) : [];
  return [sentence(lead), ...rungs].filter(Boolean).join(" ");
}
