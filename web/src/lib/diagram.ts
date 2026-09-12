/**
 * Where a Mermaid diagram starts, where it does not, and which kinds this app draws.
 *
 * The transcription writes a diagram as a ```mermaid fence, and the bank extraction copies
 * the fence's body into a field WITHOUT the fence — measured on the reference bank, every
 * `classDiagram` that reached an item's solution arrived bare. The generator then imitates
 * what the few-shot block shows it, so a generated solution is bare as often as fenced. Both
 * shapes therefore have to be recognised: the fence by its tag, the bare block by its first
 * line, which in Mermaid always names the diagram type.
 *
 * The header test is deliberately strict — `graph` and `flowchart` need a direction, `pie`
 * its own line — because a solution in an English workspace can legitimately open with the
 * word "graph" or "pie", and a paragraph drawn as a broken diagram is worse than a diagram
 * shown as text. Pure, so vitest pins it.
 *
 * `DRAWN` pairs every header with MERMAID'S OWN id for that diagram, and that second column
 * is what `vite/mermaid-subset.ts` reads: Mermaid 12 registers 38 diagram types, each behind
 * a lazy import, so all 30 this table does not name were being built and deployed as chunks
 * nothing here could ever ask for. Pairing the two in one table is what stops the gate and
 * the bundle from drifting — adding a kind is one row, and the build follows.
 */

/**
 * Each diagram this app draws: Mermaid's id for it, and how its first line opens.
 *
 * THE EIGHT KINDS `IMAGE_RULES` ASKS THE MODEL FOR, and no more: what is not asked for is
 * not written, so a wider table only built chunks nobody could reach. A kind a teacher
 * pastes that is not here is shown as its own source, which is what the header test already
 * did for prose — adding one back is this row plus a rebuild.
 */
const DRAWN: ReadonlyArray<readonly [id: string, header: RegExp]> = [
  ["flowchart-v2", /^(?:flowchart|graph)\s+(?:TD|TB|BT|RL|LR)\b/],
  ["classDiagram", /^classDiagram\s*$/],
  ["sequence", /^sequenceDiagram\s*$/],
  ["stateDiagram", /^stateDiagram(?:-v2)?\s*$/],
  ["er", /^erDiagram\s*$/],
  ["gantt", /^gantt\s*$/],
  ["mindmap", /^mindmap\s*$/],
  ["timeline", /^timeline\s*$/],
];

/** Mermaid's own ids for the diagrams above. Read by the Vite plugin, not by the app. */
export const DRAWN_DIAGRAMS: readonly string[] = DRAWN.map(([id]) => id);

const HEADERS = DRAWN.map(([, header]) => header);

const DIAGRAM_TAGS = new Set(["mermaid"]);

const FENCE = /^\s{0,3}(?:```|~~~)/m;

/** Whether a fence's language tag names a diagram rather than code. */
export function isDiagramTag(tag: string): boolean {
  return DIAGRAM_TAGS.has(tag.trim().toLowerCase());
}

/**
 * The first line that names a diagram type, skipping what Mermaid itself allows in front of
 * it — blank lines, `%%` directives and a `---` front-matter block — or `null` if there is
 * none left.
 */
function headerLine(text: string): string | null {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;
  while (index < lines.length && !lines[index].trim()) index += 1;
  if (index < lines.length && lines[index].trim() === "---") {
    index += 1;
    while (index < lines.length && lines[index].trim() !== "---") index += 1;
    index += 1;
  }
  while (index < lines.length && (!lines[index].trim() || lines[index].trimStart().startsWith("%%"))) {
    index += 1;
  }
  return index < lines.length ? lines[index].trim() : null;
}

/**
 * Whether `code` opens by naming a diagram this app draws.
 *
 * This is the gate for BOTH shapes, which is what lets the build leave out every other kind:
 * a ```mermaid fence holding a type that is not in `DRAWN` is shown as its own source, the
 * way a bare block of it already was, rather than as a diagram that cannot be loaded.
 */
export function isDrawableDiagram(code: string): boolean {
  const header = headerLine(code);
  return header !== null && HEADERS.some((pattern) => pattern.test(header));
}

/**
 * The whole of `text` when it IS a bare Mermaid diagram, `null` otherwise.
 *
 * Refuses any text carrying a fence, which the markdown layer owns.
 */
export function diagramSource(text: string): string | null {
  if (!text || FENCE.test(text)) return null;
  return isDrawableDiagram(text) ? text.trim() : null;
}
