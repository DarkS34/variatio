/**
 * The concept map's diagram, written from what the server read off the graph.
 *
 * The server sends names, relations and directions (`tutor/concept_map.py`) and no drawing:
 * the words on a map belong to the reader's interface language and its colours to the theme,
 * and both are the client's. This module writes the Mermaid source — pure, so vitest pins
 * it — and `ConceptMap.tsx` paints it.
 *
 * The prerequisite relation is drawn in the order things are learnt: what the concept takes
 * as known, an arrow into the concept, an arrow out to what comes later. Every other
 * relation of the graph is a dotted edge carrying the graph's own label, pointing the way
 * the graph does. What a cap left out is one small «and N more» node, never silence.
 */

export interface ConceptMapLink {
  name: string;
  relation: string;
  direction: string;
}

/** A turn's `concept_map`, read defensively: an older record may lack any of it. */
export interface ConceptMapData {
  concept: string;
  unit?: string;
  before?: string[];
  after?: string[];
  links?: ConceptMapLink[];
  hidden?: { before?: number; after?: number; links?: number };
  review?: string | null;
}

export interface ConceptMapWords {
  before: string;
  after: string;
  more: (n: number) => string;
}

export type ConceptMapDirection = "LR" | "TD";

// Mermaid spaces a flowchart for a page of its own (50 px between nodes and between ranks).
// A map sits under a paragraph: drawn that loose, ten boxes filled the whole conversation
// panel and pushed the reply they illustrate out of sight.
const COMPACT = '%%{init: {"flowchart": {"nodeSpacing": 14, "rankSpacing": 34, "padding": 10, "diagramPadding": 4}}}%%';

/**
 * A label as Mermaid reads it inside double quotes. `#` first, since the other two are
 * written with it; a backtick, because a quoted label that opens with one is read as
 * markdown; a line break, because a node is one line.
 */
function label(text: string): string {
  return text
    .replace(/#/g, "#35;")
    .replace(/"/g, "#quot;")
    .replace(/`/g, "#96;")
    .replace(/\s+/g, " ")
    .trim();
}

export function conceptMapSource(
  map: ConceptMapData,
  words: ConceptMapWords,
  direction: ConceptMapDirection = "LR",
): string {
  const before = map.before ?? [];
  const after = map.after ?? [];
  const links = map.links ?? [];
  const hidden = map.hidden ?? {};
  const review = map.review && before.includes(map.review) ? map.review : null;
  const lines = [COMPACT, `flowchart ${direction}`];

  // With a prerequisite to go and review, that node is the one thing to act on and the
  // concept steps back to ink: a map never asks for attention in two places.
  lines.push(`  focus(["${label(map.concept)}"]):::${review ? "anchor" : "focus"}`);

  if (before.length > 0) {
    lines.push(`  subgraph before["${label(words.before)}"]`);
    before.forEach((name, index) => {
      lines.push(`    b${index}["${label(name)}"]:::${name === review ? "review" : "known"}`);
    });
    if (hidden.before) lines.push(`    bMore["${label(words.more(hidden.before))}"]:::more`);
    lines.push("  end");
    before.forEach((_, index) => lines.push(`  b${index} --> focus`));
  }

  if (after.length > 0) {
    lines.push(`  subgraph after["${label(words.after)}"]`);
    after.forEach((name, index) => lines.push(`    a${index}["${label(name)}"]:::later`));
    if (hidden.after) lines.push(`    aMore["${label(words.more(hidden.after))}"]:::more`);
    lines.push("  end");
    after.forEach((_, index) => lines.push(`  focus --> a${index}`));
  }

  links.forEach((link, index) => {
    const node = `l${index}["${label(link.name)}"]:::tied`;
    const text = `|"${label(link.relation)}"|`;
    if (link.direction === "in") lines.push(`  ${node} -.->${text} focus`);
    else if (link.direction === "out") lines.push(`  focus -.->${text} ${node}`);
    else lines.push(`  focus -.-${text} ${node}`);
  });
  if (links.length > 0 && hidden.links) {
    lines.push(`  focus -.- lMore["${label(words.more(hidden.links))}"]:::more`);
  }

  if (direction === "TD") lines.push(...stacked(map));
  return lines.join("\n");
}

/**
 * Invisible links that stand each group of a top-down map in a column of its own.
 *
 * A top-down flowchart lays the nodes of one rank side by side, so three dependents and
 * three related concepts made a row six boxes wide — on a phone, scaled down to text nobody
 * can read. Chained by links Mermaid lays out but does not draw, each group takes one rank
 * per node instead, and the map is as narrow as its two widest boxes.
 */
function stacked(map: ConceptMapData): string[] {
  const hidden = map.hidden ?? {};
  const links = map.links ?? [];
  const column = (ids: string[]) => (ids.length > 1 ? [`  ${ids.join(" ~~~ ")}`] : []);
  const range = (prefix: string, n: number, more?: number) => [
    ...Array.from({ length: n }, (_, index) => `${prefix}${index}`),
    ...(n > 0 && more ? [`${prefix}More`] : []),
  ];
  const above = links.flatMap((link, index) => (link.direction === "in" ? [`l${index}`] : []));
  const below = links.flatMap((link, index) => (link.direction === "in" ? [] : [`l${index}`]));
  if (links.length > 0 && hidden.links) below.push("lMore");
  return [
    ...column(range("b", map.before?.length ?? 0, hidden.before)),
    ...column(range("a", map.after?.length ?? 0, hidden.after)),
    ...column(above),
    ...column(below),
  ];
}

/**
 * The map a narrow screen draws: the learning order alone.
 *
 * Even stacked, the other relations add a second column and their labels a third, and a
 * phone scaled that down to 8 px text. So the drawing keeps what a map is for — what comes
 * before and after — and the caller writes the other relations as a line of text under it.
 */
export function narrowed(map: ConceptMapData): ConceptMapData {
  return { ...map, links: [] };
}

/**
 * Whether a turn's map has anything to draw: a concept, and something before or after it.
 * The server sends no other kind; an older or a damaged record is simply not drawn.
 */
export function isDrawable(map: ConceptMapData | null | undefined): map is ConceptMapData {
  if (!map || typeof map.concept !== "string" || !map.concept) return false;
  return (map.before?.length ?? 0) + (map.after?.length ?? 0) > 0;
}
