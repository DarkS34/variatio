/**
 * The concept map, as the server reads it off the graph and the client draws it.
 *
 * The server sends names, relations and directions (`tutor/concept_map.py`) and no drawing:
 * the words on a map belong to the reader's interface language and its colours to the theme,
 * and both are the client's. `ConceptMap.tsx` lays it out with the app's own chips and draws
 * the lines between them; the geometry of those lines is here, pure, so vitest can pin it.
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

/**
 * Whether a turn's map has anything to draw: a concept, and something before or after it.
 * The server sends no other kind; an older or a damaged record is simply not drawn.
 */
export function isDrawable(map: ConceptMapData | null | undefined): map is ConceptMapData {
  if (!map || typeof map.concept !== "string" || !map.concept) return false;
  return (map.before?.length ?? 0) + (map.after?.length ?? 0) > 0;
}

/** The prerequisite a map marks as the one to go over, when it is one the map draws. */
export function reviewOf(map: ConceptMapData): string | null {
  return map.review && (map.before ?? []).includes(map.review) ? map.review : null;
}

/**
 * Whether a relation that is not the learning order points INTO the concept. Those are
 * drawn on the concept's left, read «Caso base se engloba en» towards it; the rest — out of
 * it or with no direction — on its right, read «se engloba en Abstracción» away from it.
 */
export function pointsIn(link: ConceptMapLink): boolean {
  return link.direction === "in";
}

/** A box on the map, in pixels from the top left of the figure. */
export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export type Side = "left" | "right" | "above" | "below";

/**
 * Where a node stands relative to the concept. The layout decides it — side by side on a
 * wide figure, stacked on a narrow one — and the lines follow whatever the layout did.
 */
export function sideOf(node: Box, concept: Box): Side {
  if (node.right <= concept.left) return "left";
  if (node.left >= concept.right) return "right";
  return node.top + node.bottom < concept.top + concept.bottom ? "above" : "below";
}

/** Half a pixel is the grain a one-pixel line is drawn crisp at. */
function px(value: number): number {
  return Math.round(value * 2) / 2;
}

/** A smooth curve between two points, leaving and arriving level. */
export function curve(x1: number, y1: number, x2: number, y2: number): string {
  const mid = px((x1 + x2) / 2);
  return `M${px(x1)} ${px(y1)}C${mid} ${px(y1)} ${mid} ${px(y2)} ${px(x2)} ${px(y2)}`;
}

/**
 * A line that leaves the concept to the left, runs down a rail at `x` and turns into a node
 * below: how a narrow figure reaches the relations it lists under everything else, without
 * crossing the concepts in between. Its two turns are rounded.
 */
export function rail(x1: number, y1: number, x: number, x2: number, y2: number): string {
  const r = Math.min(8, Math.abs(y2 - y1) / 2);
  return [
    `M${px(x1)} ${px(y1)}`,
    `H${px(x + r)}`,
    `Q${px(x)} ${px(y1)} ${px(x)} ${px(y1 + r)}`,
    `V${px(y2 - r)}`,
    `Q${px(x)} ${px(y2)} ${px(x + r)} ${px(y2)}`,
    `H${px(x2)}`,
  ].join("");
}
