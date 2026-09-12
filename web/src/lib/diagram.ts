/**
 * Where a Mermaid diagram starts, and where it does not.
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
 */

const DIAGRAM_TAGS = new Set(["mermaid"]);

const HEADERS: RegExp[] = [
  /^(?:flowchart|graph)\s+(?:TD|TB|BT|RL|LR)\b/,
  /^(?:classDiagram|sequenceDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|mindmap|timeline|quadrantChart|requirementDiagram|kanban|xychart-beta|block-beta|sankey-beta|packet-beta|architecture-beta|usecase-beta)\s*$/,
  /^pie(?:\s+showData)?(?:\s+title\b.*)?\s*$/,
  /^gitGraph(?:\s+(?:LR|TB|BT):?)?\s*$/,
  /^C4(?:Context|Container|Component|Dynamic|Deployment)\s*$/,
];

const FENCE = /^\s{0,3}(?:```|~~~)/m;

/** Whether a fence's language tag names a diagram rather than code. */
export function isDiagramTag(tag: string): boolean {
  return DIAGRAM_TAGS.has(tag.trim().toLowerCase());
}

/**
 * The whole of `text` when it IS a bare Mermaid diagram, `null` otherwise.
 *
 * Skips what Mermaid itself allows before the header — blank lines, `%%` directives and a
 * `---` front-matter block — and refuses any text carrying a fence, which the markdown
 * layer owns.
 */
export function diagramSource(text: string): string | null {
  if (!text || FENCE.test(text)) return null;
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
  if (index >= lines.length) return null;
  const header = lines[index].trim();
  return HEADERS.some((pattern) => pattern.test(header)) ? text.trim() : null;
}
