import { TONE_VAR } from "@/lib/status";
import type { GraphView } from "@/lib/types";

import type { LabelGrid } from "./labels";
import type { Body, Frame, LayoutMode } from "./layout";
import type { Lane } from "./mapLayout";
import type { GraphModel } from "./model";
import { CONCEPT_SIDE, type Region } from "./regions";

/**
 * THE MAP, PAINTED AT THE LEVEL OF DETAIL THE ZOOM CAN SHOW.
 *
 * A subject of ten thousand concepts cannot be read all at once, and a picture that tries is
 * a grey mass. So what is drawn depends on how far apart two concepts are ON SCREEN. Far out,
 * the units are the map: each region is named in the middle, its concepts are specks of its
 * colour, and the relations between units are drawn once per pair, as thick as they are many.
 * Closer, the concepts take over: their own lines, their discs, and the unit's name moves to a
 * header that stays in view while any of the unit is. It is the approach sigma.js takes for
 * large graphs, without the library: names compete for room in a screen grid (`labels.ts`),
 * the most connected first, so what is written is always readable and zooming in reveals more.
 *
 * Everything off screen is skipped, so a frame costs what is visible and not what exists.
 */

export interface Palette {
  foreground: string;
  muted: string;
  border: string;
  background: string;
  accent: string;
  /** The three frontier tones. Their names come from `lib/status` and not from string
   *  literals repeated here: that is what stops the curriculum view painting "covered" in
   *  a different green from the one the navbar uses. */
  settled: string;
  attention: string;
  ahead: string;
  /** The application's sans face, read off `--font-sans`: a canvas inherits no CSS. */
  font: string;
}

export interface View {
  x: number;
  y: number;
  scale: number;
}

export type LabelMode = "auto" | "all" | "none";

export interface Scene {
  graph: GraphView;
  model: GraphModel;
  bodies: Body[];
  view: View;
  frame: Frame;
  palette: Palette;
  mode: LayoutMode;
  labels: LabelMode;
  arrows: boolean;
  /** The units' regions and lanes — from the plan alone while the concepts are being placed. */
  regions: Region[];
  lanes: Lane[];
  /** Per unit, "N conceptos", already in the reader's language. */
  unitCounts: string[];
  /** "N sin relaciones": the painter takes the sentence, never the catalogue. */
  laneCaption: (count: number) => string;
  compact: boolean;
  /** Whether the bodies are easing between views or the camera is flying, this frame. */
  moving: boolean;
  selected: number;
  picked?: Set<number>;
  focused: number;
  highlight?: Set<string>;
  hiddenRelations?: Set<number>;
  /** Node indices the course has already covered. `undefined` — not an empty set — means
   *  no curriculum is in force, and everything keeps its domain colour. */
  curriculum?: Set<number>;
  /** Covered nothing, but every prerequisite covered: what can be taught next. */
  frontier?: Set<number>;
  /** Screen-space room for names, reset every frame. */
  grid: LabelGrid;
  /** Screen boxes no name may cover — the canvas's own toolbars and minimap. */
  reserved: [number, number, number, number][];
  /** Each concept's name width at the label size, measured once and kept: NaN until then. */
  widths: Float32Array;
  /** Scratch, per concept: whether it is on screen this frame. */
  onScreen: Uint8Array;
}

const TAU = Math.PI * 2;
const LABEL_SIZE = 11;
const CURVE = 0.14;
const ARROW = 7;
const DIM = 0.12;
// However much room there is, no frame writes more names than this: past it the measuring is
// what costs, and nobody reads six hundred names on one screen.
const MAX_LABELS = 600;
// While the bodies ease between views or the camera flies, a frame with more edges than this on
// screen leaves them to the frame that lands: they are lines in transit nobody can follow, and
// measured on a 10 000-concept subject they were the transition — switching to the order view
// went from 1.57 s of long tasks to 0.18 s, and selecting a concept from 2.39 s to 0.41 s.
const MOVING_EDGE_BUDGET = 6000;
// How far into the concepts the view is, as the distance between two neighbours ON SCREEN: at
// FROM a concept is a speck of its unit, at TO its relations are drawn in full.
const DETAIL_FROM = 6;
const DETAIL_TO = 16;
// Concepts' names start to compete for room at NAMES_FROM, and across HANDOVER around it the
// unit's name in the middle of its region hands over to the header in its corner.
const NAMES_FROM = 14;
const HANDOVER = 3;
// Far out, a unit's name that only fits its region by cutting its words may take more lines, up
// to MAX_NAME_LINES, or spill past the region's sides — up to this much of the canvas — where
// nothing else is written.
const SPILL_SHARE = 0.3;
const SPILL_WIDTH = 150;
const MAX_NAME_LINES = 4;
// A region at least ALWAYS_NAMED wide on screen is always named in its middle, cut if it has to
// be; a narrower one, down to NAMED_FROM, is named only where there is room for the whole name.
const ALWAYS_NAMED = 56;
const NAMED_FROM = 24;
/** The zoom a jump to one concept lands at: neighbours about sixty pixels apart. */
export const READING_SCALE = 60 / CONCEPT_SIDE;

/** 0 when the view is out among the units, 1 when it is in among the concepts. */
export function detailAt(scale: number) {
  return smoothstep(DETAIL_FROM, DETAIL_TO, CONCEPT_SIDE * scale);
}

/**
 * A node's radius in WORLD units, for the zoom it is drawn at.
 *
 * Divided by √scale: drawn under `context.scale`, a fixed world radius grows on screen as
 * fast as the zoom, so a hub becomes a coin over its neighbours' labels. This way it grows
 * with the square root — twice as big at 4×, not four times — and zoomed out it shrinks
 * more slowly than the drawing. The floor on the scale stops a very zoomed-out view drawing a
 * node bigger than its edges.
 */
export function radiusOf(degree: number, scale = 1) {
  return (3 + Math.min(7, Math.sqrt(degree) * 1.9)) / Math.sqrt(Math.max(0.3, scale));
}

/** The radius a concept is actually drawn at: out in the overview it shrinks to a speck. */
export function drawnRadius(degree: number, scale: number, detail: number) {
  const radius = radiusOf(degree, scale);
  return detail >= 1 ? radius : Math.max(radius * (0.3 + 0.7 * detail), 1.3 / scale);
}

export function readPalette(): Palette {
  const styles = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) =>
    styles.getPropertyValue(name).trim() || fallback;
  // The fallbacks must be the CURRENT tokens: a canvas that paints before the stylesheet
  // lands otherwise draws a palette the file has retired, and `check:color` cannot see a
  // literal outside `index.css`.
  return {
    foreground: read("--foreground", "oklch(0.18 0.008 265)"),
    muted: read("--muted-foreground", "oklch(0.47 0.012 265)"),
    border: read("--border", "oklch(0.87 0.004 265)"),
    background: read("--card", "oklch(1 0 265)"),
    accent: read("--primary", "oklch(0.20 0.010 265)"),
    settled: read(TONE_VAR.settled, "oklch(0.52 0.012 265)"),
    attention: read(TONE_VAR.attention, "oklch(0.48 0.19 262)"),
    ahead: read(TONE_VAR.muted, "oklch(0.47 0.012 265)"),
    font: read("--font-sans", '"Archivo Variable", "Archivo", ui-sans-serif, system-ui'),
  };
}

function smoothstep(from: number, to: number, value: number) {
  const t = Math.min(1, Math.max(0, (value - from) / (to - from)));
  return t * t * (3 - 2 * t);
}

// The same calculation the generator already performs for every commission — assumed_known
// / target / forbidden — drawn. Outside the curriculum view the colour stays the domain's:
// there, what you read is what each concept is ABOUT, not the order it is taught in.
function nodeFill(scene: Scene, index: number, group: number): string {
  const { palette, model } = scene;
  if (scene.mode !== "curriculum" || !scene.curriculum) {
    return model.domainColours[group] ?? palette.muted;
  }
  if (scene.frontier?.has(index)) return palette.attention;
  if (scene.curriculum.has(index)) return palette.settled;
  return palette.ahead;
}

/** Midpoint of the arc an edge is drawn along. Every edge bows the same way, which is
 *  what keeps a pair stated in both directions from collapsing into one line, and what
 *  lets an arrowhead sit on a tangent instead of on top of the target node. */
function control(ax: number, ay: number, bx: number, by: number) {
  const deltaX = bx - ax;
  const deltaY = by - ay;
  return {
    x: (ax + bx) / 2 - deltaY * CURVE,
    y: (ay + by) / 2 + deltaX * CURVE,
  };
}

function pointAt(t: number, a: number, c: number, b: number) {
  const inverse = 1 - t;
  return inverse * inverse * a + 2 * inverse * t * c + t * t * b;
}

interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

interface Candidate {
  index: number;
  x: number;
  y: number;
  priority: number;
  strong: boolean;
  dim: boolean;
}

export function draw(context: CanvasRenderingContext2D, scene: Scene) {
  const { graph, bodies, view, frame } = scene;
  const { width, height } = frame;
  if (width === 0 || height === 0) return;

  const ratio = Math.min(2, window.devicePixelRatio || 1);
  const { scale } = view;
  const force = scene.mode === "force";
  const detail = force ? detailAt(scale) : 1;

  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);

  // The world rectangle on screen, padded so a disc half in view is still drawn.
  const pad = 40 / scale;
  const box: Box = {
    left: (-width / 2 - view.x) / scale - pad,
    right: (width / 2 - view.x) / scale + pad,
    top: (-height / 2 - view.y) / scale - pad,
    bottom: (height / 2 - view.y) / scale + pad,
  };
  const count = Math.min(graph.nodes.length, bodies.length);
  let visible = 0;
  for (let index = 0; index < count; index += 1) {
    const body = bodies[index];
    const inside =
      body.x >= box.left && box.right >= body.x && body.y >= box.top && box.bottom >= body.y;
    scene.onScreen[index] = inside ? 1 : 0;
    if (inside) visible += 1;
  }

  const focus = scene.focused >= 0 ? scene.focused : scene.selected;
  const near = focus >= 0 ? scene.model.adjacency.get(focus) : undefined;

  context.save();
  context.translate(width / 2 + view.x, height / 2 + view.y);
  context.scale(scale, scale);
  if (force) drawRegions(context, scene, focus >= 0);
  else drawLevels(context, scene);
  let candidates: Candidate[] = [];
  if (count > 0) {
    const share = visible / Math.max(1, graph.nodes.length);
    if (force && detail < 1) drawUnitLinks(context, scene, 1 - detail);
    if (!scene.moving || MOVING_EDGE_BUDGET >= graph.links.length * share) {
      drawEdges(context, scene, box, focus, detail, share);
    }
    candidates = drawNodes(context, scene, focus, near, detail, count);
  }
  context.restore();

  // Everything sized in PIXELS is drawn after the world, in screen space: a name never scales
  // with the zoom. The units' names go first, so the concepts' names give way to them.
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  scene.grid.reset(width, height);
  // The toolbars and the minimap sit over the canvas: a name written under them is a name
  // nobody can read, so their boxes are taken before any name competes.
  for (const [x0, y0, x1, y1] of scene.reserved) scene.grid.place(x0, y0, x1, y1, true);
  if (force) drawUnitNames(context, scene, detail);
  if (candidates.length > 0) drawLabels(context, scene, candidates);
  context.globalAlpha = 1;
}

/** Each unit's region: a tint of its colour, a hairline, and the rule over its lane. */
function drawRegions(context: CanvasRenderingContext2D, scene: Scene, focusing: boolean) {
  const { model, view, palette, regions, lanes } = scene;
  for (const region of regions) {
    context.globalAlpha = focusing ? 0.035 : 0.07;
    context.fillStyle = model.domainColours[region.group] ?? palette.muted;
    context.fillRect(region.x, region.y, region.width, region.height);
  }
  context.globalAlpha = 1;
  context.strokeStyle = palette.border;
  context.lineWidth = 1 / view.scale;
  for (const region of regions) {
    context.strokeRect(region.x, region.y, region.width, region.height);
  }
  if (lanes.length === 0) return;
  context.beginPath();
  for (const lane of lanes) {
    const region = regions.find((entry) => entry.group === lane.group);
    if (!region) continue;
    context.moveTo(region.x + 12, lane.top);
    context.lineTo(region.x + region.width - 12, lane.top);
  }
  context.setLineDash([4 / view.scale, 4 / view.scale]);
  context.stroke();
  context.setLineDash([]);
}

/**
 * The relations between units, one line per pair, while the view is too far out to draw a
 * concept's own. Thicker for more, and faint: it says which units lean on which, not how.
 */
function drawUnitLinks(context: CanvasRenderingContext2D, scene: Scene, strength: number) {
  const { model, view, palette, regions } = scene;
  if (model.unitLinks.length === 0 || strength <= 0.01) return;
  const byGroup = new Map(regions.map((region) => [region.group, region]));
  const busiest = model.unitLinks[0][2];
  context.strokeStyle = palette.muted;
  context.lineCap = "round";
  // The forty busiest pairs only, and light: measured on fourteen units, all ninety-one pairs
  // at full weight crossed the middle of the map as a dark lattice over the regions they join.
  for (const [a, b, links] of model.unitLinks.slice(0, 40)) {
    const from = byGroup.get(a);
    const to = byGroup.get(b);
    if (!from || !to) continue;
    const [x1, y1] = exit(from, to);
    const [x2, y2] = exit(to, from);
    context.globalAlpha = strength * (0.05 + 0.22 * (links / busiest));
    context.lineWidth = (0.6 + Math.log2(1 + links) * 0.55) / view.scale;
    context.beginPath();
    context.moveTo(x1, y1);
    context.lineTo(x2, y2);
    context.stroke();
  }
  context.lineCap = "butt";
  context.globalAlpha = 1;
}

/** Where the line from one region's centre toward another's leaves the first region. */
function exit(from: Region, to: Region): [number, number] {
  const cx = from.x + from.width / 2;
  const cy = from.y + from.height / 2;
  const dx = to.x + to.width / 2 - cx;
  const dy = to.y + to.height / 2 - cy;
  const reach = Math.min(
    Math.abs(dx) > 1e-6 ? from.width / 2 / Math.abs(dx) : Infinity,
    Math.abs(dy) > 1e-6 ? from.height / 2 / Math.abs(dy) : Infinity,
  );
  return Number.isFinite(reach) ? [cx + dx * reach, cy + dy * reach] : [cx, cy];
}

function drawEdges(
  context: CanvasRenderingContext2D,
  scene: Scene,
  box: Box,
  focus: number,
  detail: number,
  share: number,
) {
  const { graph, model, bodies, view, palette } = scene;
  const { scale } = view;
  const hidden = scene.hiddenRelations;

  // Ink is budgeted by the edges ON SCREEN: the alpha that reads as "a few lines" on 180 of
  // them reads as a grey wash on 500, and the wash is what buries the nodes. Arrowheads wait
  // until the zoom can show one.
  const density = Math.min(1, (graph.links.length * share) / 260);
  const restAlpha = (0.42 - density * 0.2) * detail;
  const showArrows = scene.arrows && detail >= 0.99 && CONCEPT_SIDE * scale > 24 + density * 16;

  // Ink follows meaning: the prerequisite relation is the one the whole pedagogy runs on, so
  // it gets more ink than the rest; the catch-all gets less. In the curriculum view — which
  // IS the prerequisite order — the relations that do not order anything fade to a whisper.
  const inkOf = (relation: number): { alpha: number; width: number } => {
    const meta = graph.relations[relation];
    let alpha = restAlpha;
    let width = 1;
    if (meta?.prerequisite) {
      alpha = Math.min(0.62, restAlpha * 1.5);
      width = 1.4;
    } else if (meta && !meta.directed) {
      alpha = restAlpha * 0.7;
      width = 0.8;
    }
    if (scene.mode === "curriculum" && !meta?.prerequisite) alpha *= 0.28;
    return { alpha, width };
  };

  const focused: number[] = [];
  for (let relation = 0; relation < graph.relations.length; relation += 1) {
    if (hidden?.has(relation)) continue;
    const bucket = model.linkBuckets[relation];
    if (!bucket || bucket.length === 0) continue;
    const ink = inkOf(relation);
    const alpha = focus >= 0 ? 0.07 * detail : ink.alpha;
    const drawing = alpha > 0.004;
    if (!drawing && focus < 0) continue;
    context.strokeStyle = model.relationColours[relation] ?? palette.border;
    context.globalAlpha = alpha;
    context.lineWidth = ink.width / scale;
    context.beginPath();
    let drawn = 0;
    for (let k = 0; k < bucket.length; k += 1) {
      const link = graph.links[bucket[k]];
      const source = link[0];
      const target = link[1];
      if (focus >= 0 && (source === focus || target === focus)) {
        focused.push(bucket[k]);
        continue;
      }
      if (!drawing) continue;
      const a = bodies[source];
      const b = bodies[target];
      if (!a || !b || offScreen(a, b, box)) continue;
      const c = control(a.x, a.y, b.x, b.y);
      context.moveTo(a.x, a.y);
      context.quadraticCurveTo(c.x, c.y, b.x, b.y);
      drawn += 1;
    }
    if (drawn > 0) context.stroke();
  }

  if (showArrows && focus < 0) {
    for (let relation = 0; relation < graph.relations.length; relation += 1) {
      if (hidden?.has(relation) || !graph.relations[relation].directed) continue;
      const bucket = model.linkBuckets[relation];
      if (!bucket) continue;
      context.fillStyle = model.relationColours[relation] ?? palette.border;
      context.globalAlpha = inkOf(relation).alpha;
      for (let k = 0; k < bucket.length; k += 1) {
        const [source, target] = graph.links[bucket[k]];
        const a = bodies[source];
        const b = bodies[target];
        if (!a || !b || offScreen(a, b, box)) continue;
        arrowhead(context, scene, source, target);
      }
    }
  }

  for (const linkIndex of focused) {
    const [source, target, relation] = graph.links[linkIndex];
    const a = bodies[source];
    const b = bodies[target];
    if (!a || !b) continue;
    context.strokeStyle = model.relationColours[relation] ?? palette.foreground;
    context.globalAlpha = 0.95;
    context.lineWidth = 2 / scale;
    const c = control(a.x, a.y, b.x, b.y);
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.quadraticCurveTo(c.x, c.y, b.x, b.y);
    context.stroke();
    if (scene.arrows && graph.relations[relation]?.directed) {
      context.fillStyle = model.relationColours[relation] ?? palette.foreground;
      arrowhead(context, scene, source, target);
    }
  }
  context.globalAlpha = 1;
}

function offScreen(a: Body, b: Body, box: Box) {
  return (
    Math.max(a.x, b.x) < box.left ||
    Math.min(a.x, b.x) > box.right ||
    Math.max(a.y, b.y) < box.top ||
    Math.min(a.y, b.y) > box.bottom
  );
}

/** The head sits where the curve meets the target's rim, on the curve's own tangent. */
function arrowhead(
  context: CanvasRenderingContext2D,
  scene: Scene,
  source: number,
  target: number,
) {
  const a = scene.bodies[source];
  const b = scene.bodies[target];
  if (!a || !b) return;
  const radius = radiusOf(scene.model.degrees[target] ?? 0, scene.view.scale);
  const c = control(a.x, a.y, b.x, b.y);

  const distance = Math.hypot(b.x - a.x, b.y - a.y);
  if (distance < radius * 2.5) return;
  const t = Math.max(0, 1 - (radius + 2) / distance);
  const tipX = pointAt(t, a.x, c.x, b.x);
  const tipY = pointAt(t, a.y, c.y, b.y);
  const backX = pointAt(t - 0.06, a.x, c.x, b.x);
  const backY = pointAt(t - 0.06, a.y, c.y, b.y);
  const angle = Math.atan2(tipY - backY, tipX - backX);
  const size = ARROW / scene.view.scale;

  context.beginPath();
  context.moveTo(tipX, tipY);
  context.lineTo(tipX - Math.cos(angle - 0.42) * size, tipY - Math.sin(angle - 0.42) * size);
  context.lineTo(tipX - Math.cos(angle + 0.42) * size, tipY - Math.sin(angle + 0.42) * size);
  context.closePath();
  context.fill();
}

/**
 * The concepts on screen, one path per colour — ten thousand separate fills would be the frame
 * — and the names that could be written beside them, returned to compete for room.
 */
function drawNodes(
  context: CanvasRenderingContext2D,
  scene: Scene,
  focus: number,
  near: Set<number> | undefined,
  detail: number,
  count: number,
): Candidate[] {
  const { graph, model, bodies, view, palette, onScreen } = scene;
  const { scale } = view;
  const fills = new Map<string, Path2D>();
  const faint = new Map<string, Path2D>();
  const hollow = new Path2D();
  const hollowFaint = new Path2D();
  let hollows = 0;
  let hollowsFaint = 0;
  const rings: number[] = [];
  const candidates: Candidate[] = [];

  const spacing = CONCEPT_SIDE * scale;
  const naming = scene.labels !== "none";
  // Whether ordinary concepts may be named at all at this zoom. In the order view concepts sit
  // on a fixed grid, so its own threshold is the zoom and not the map's spacing.
  const crowd =
    scene.mode === "force"
      ? spacing >= (scene.labels === "all" ? 6 : NAMES_FROM)
      : scene.labels === "all" || scale >= 0.55;
  const fewMarked = Boolean(scene.highlight && scene.highlight.size <= 40);

  for (let index = 0; index < count; index += 1) {
    if (!onScreen[index]) continue;
    const body = bodies[index];
    const [name, group, nonTaggable] = graph.nodes[index];
    const isFocus = index === focus;
    const isNear = near?.has(index) ?? false;
    const isMarked = scene.highlight ? scene.highlight.has(name) : true;
    const isPicked = scene.picked?.has(index) ?? false;
    const dimmed = !isPicked && ((focus >= 0 && !isFocus && !isNear) || !isMarked);
    const radius = drawnRadius(model.degrees[index] ?? 0, scale, detail);

    const colour = isPicked ? palette.accent : nodeFill(scene, index, group);
    const paths = dimmed ? faint : fills;
    let path = paths.get(colour);
    if (!path) {
      path = new Path2D();
      paths.set(colour, path);
    }
    path.moveTo(body.x + radius, body.y);
    path.arc(body.x, body.y, radius, 0, TAU);

    // A non-taggable concept is in the graph for its relations only: nothing is ever
    // labelled with it. Drawn hollow, so it reads as structure rather than as a target.
    const inner = radius - 1.6 / scale;
    if (nonTaggable && inner > 0.8 / scale) {
      const target = dimmed ? hollowFaint : hollow;
      target.moveTo(body.x + inner, body.y);
      target.arc(body.x, body.y, inner, 0, TAU);
      if (dimmed) hollowsFaint += 1;
      else hollows += 1;
    }

    if (isPicked || index === scene.selected) rings.push(index);

    if (!naming) continue;
    const strong = isFocus || index === scene.selected || isPicked;
    const marked = fewMarked && isMarked;
    if (strong || isNear || marked || (crowd && !dimmed)) {
      candidates.push({
        index,
        x: body.x,
        y: body.y - radius - 3 / scale,
        strong,
        dim: dimmed && !isNear,
        priority: strong ? 4 : isNear ? 3 : marked ? 2 : 1,
      });
    }
  }

  context.globalAlpha = 1;
  for (const [colour, path] of fills) {
    context.fillStyle = colour;
    context.fill(path);
  }
  context.globalAlpha = DIM;
  for (const [colour, path] of faint) {
    context.fillStyle = colour;
    context.fill(path);
  }
  context.fillStyle = palette.background;
  if (hollows > 0) {
    context.globalAlpha = 0.9;
    context.fill(hollow);
  }
  if (hollowsFaint > 0) {
    context.globalAlpha = DIM;
    context.fill(hollowFaint);
  }

  context.globalAlpha = 1;
  for (const index of rings) {
    const body = bodies[index];
    const radius = drawnRadius(model.degrees[index] ?? 0, scale, detail);
    if (scene.picked?.has(index)) {
      context.strokeStyle = palette.accent;
      context.lineWidth = 2 / scale;
      context.beginPath();
      context.arc(body.x, body.y, radius + 3 / scale, 0, TAU);
      context.stroke();
    }
    if (index === scene.selected) {
      context.strokeStyle = palette.foreground;
      context.lineWidth = 2.5 / scale;
      context.beginPath();
      context.arc(body.x, body.y, radius + 4 / scale, 0, TAU);
      context.stroke();
    }
  }
  return candidates;
}

/**
 * The names, placed most important first into the screen grid: the one being looked at, its
 * neighbours, a short search's matches, then by how connected a concept is. A name with no
 * room is not drawn — zooming in makes the room.
 */
function drawLabels(context: CanvasRenderingContext2D, scene: Scene, candidates: Candidate[]) {
  const { graph, model, view, frame, palette, grid, widths } = scene;
  candidates.sort(
    (a, b) =>
      b.priority - a.priority || (model.degrees[b.index] ?? 0) - (model.degrees[a.index] ?? 0),
  );
  const originX = frame.width / 2 + view.x;
  const originY = frame.height / 2 + view.y;
  context.font = `400 ${LABEL_SIZE}px ${palette.font}`;
  const chosen: { text: string; x: number; y: number; strong: boolean; dim: boolean }[] = [];
  for (const candidate of candidates) {
    if (!candidate.strong && chosen.length >= MAX_LABELS) break;
    const x = candidate.x * view.scale + originX;
    const y = candidate.y * view.scale + originY;
    if (-LABEL_SIZE > y || y > frame.height + LABEL_SIZE) continue;
    const text = graph.nodes[candidate.index][0];
    let width = widths[candidate.index];
    if (Number.isNaN(width)) {
      width = context.measureText(text).width;
      widths[candidate.index] = width;
    }
    const half = (candidate.strong ? width * 1.07 : width) / 2 + 3;
    if (!grid.place(x - half, y - LABEL_SIZE, x + half, y + 3, candidate.strong)) continue;
    chosen.push({ text, x, y, strong: candidate.strong, dim: candidate.dim });
  }

  context.textAlign = "center";
  context.textBaseline = "alphabetic";
  context.lineJoin = "round";
  context.lineWidth = 3;
  context.strokeStyle = palette.background;
  for (const strong of [false, true]) {
    context.font = `${strong ? 600 : 400} ${LABEL_SIZE}px ${palette.font}`;
    context.fillStyle = strong ? palette.foreground : palette.muted;
    for (const label of chosen) {
      if (label.strong !== strong) continue;
      // A halo under the text, so a name crossing an edge stays readable without hiding it.
      context.globalAlpha = label.dim ? 0.35 : 1;
      context.strokeText(label.text, label.x, label.y);
      context.fillText(label.text, label.x, label.y);
    }
  }
  context.globalAlpha = 1;
}

/**
 * Each unit's name. Far out it is written in the middle of its region, as large as the region
 * allows, with how many concepts it holds; closer in it becomes a header in the region's corner
 * that stays in view while any of the region is, so the unit being read is always named.
 */
function drawUnitNames(context: CanvasRenderingContext2D, scene: Scene, detail: number) {
  const { graph, model, view, frame, palette, grid, regions, lanes } = scene;
  if (regions.length === 0) return;
  const originX = frame.width / 2 + view.x;
  const originY = frame.height / 2 + view.y;
  const spacing = CONCEPT_SIDE * view.scale;
  // One curve read both ways, so at no zoom is a unit left without a name at full ink: the
  // staggered fades this replaced had the enlarged view open with every name at half opacity
  // over its concepts. While both are partly drawn the middle one holds its room in the grid,
  // so the concepts' own names, which start at NAMES_FROM, are written around it.
  const header = smoothstep(NAMES_FROM - 1, NAMES_FROM - 1 + HANDOVER, spacing);
  const centred = 1 - header;
  context.textBaseline = "alphabetic";
  context.lineJoin = "round";

  // Largest first: a big unit's name fits inside its own region, so it takes its room before a
  // small neighbour's name asks to spill into it.
  const order = [...regions].sort((a, b) => b.width * b.height - a.width * a.height);
  for (const region of order) {
    const x0 = region.x * view.scale + originX;
    const y0 = region.y * view.scale + originY;
    const w = region.width * view.scale;
    const h = region.height * view.scale;
    if (x0 > frame.width || y0 > frame.height || x0 + w < 0 || y0 + h < 0) continue;
    const name = graph.groups[region.group]?.name ?? "";
    if (centred > 0.02 && w >= NAMED_FROM && h >= 34) {
      centredName(context, scene, name, scene.unitCounts[region.group] ?? "", x0, y0, w, h, centred);
    }
    if (header > 0.02 && w >= 80) {
      const colour = model.domainColours[region.group] ?? palette.muted;
      headerName(context, scene, name, colour, x0, y0, w, h, header);
    }
  }

  if (detail > 0.5) {
    context.font = `400 10px ${palette.font}`;
    context.textAlign = "left";
    context.fillStyle = palette.muted;
    for (const lane of lanes) {
      const region = regions.find((entry) => entry.group === lane.group);
      if (!region) continue;
      const x = (region.x + 12) * view.scale + originX;
      const y = lane.top * view.scale + originY + 13;
      if (x > frame.width || y > frame.height || 0 > y) continue;
      const text = scene.laneCaption(lane.count);
      const width = context.measureText(text).width;
      if (!grid.place(x - 2, y - 11, x + width + 2, y + 3)) continue;
      context.globalAlpha = Math.min(1, (detail - 0.5) * 2) * 0.9;
      context.fillText(text, x, y);
    }
  }
  context.globalAlpha = 1;
}

function centredName(
  context: CanvasRenderingContext2D,
  scene: Scene,
  name: string,
  count: string,
  x0: number,
  y0: number,
  w: number,
  h: number,
  alpha: number,
) {
  const { palette, grid, compact, frame } = scene;
  const size = Math.round(Math.min(compact ? 15 : 22, Math.max(11, Math.min(w, h) * 0.09)));
  const maxLines = h >= size * 5 ? 3 : 2;
  const countSize = Math.max(10, Math.round(size * 0.62));
  const lineHeight = size * 1.18;
  context.font = `400 ${countSize}px ${palette.font}`;
  const countWidth = count ? context.measureText(count).width : 0;
  const countBlock = count ? countSize * 1.6 : 0;
  context.font = `600 ${size}px ${palette.font}`;

  // Kept inside the canvas, so a region at its edge does not push its own name, or the count
  // under it, out of view — but never so far that the middle of the name leaves its region.
  const layout = (lines: string[]) => {
    const widest = Math.max(countWidth, ...lines.map((line) => context.measureText(line).width));
    const half = widest / 2 + 4;
    const height = lines.length * lineHeight + countBlock;
    const cx = within(x0 + w / 2, half, frame.width - half, x0, x0 + w);
    const middle = within(y0 + h / 2, height / 2 + 2, frame.height - height / 2 - 2, y0, y0 + h);
    const top = middle - height / 2;
    return { lines, cx, top, left: cx - half, right: cx + half, bottom: top + height };
  };

  const inside = Math.max(40, w * 0.86);
  const spill = Math.max(inside, Math.min(frame.width * SPILL_SHARE, SPILL_WIDTH));
  const tight = wrap(context, name, inside, maxLines);
  // The shapes a name may take: as it fits its region; wider than the region, on the lines it
  // had; and, when neither keeps every word, as narrow as its longest word allows on as many
  // lines as the region has room for. Only a shape that keeps every word is tried, fewest lines
  // first, and only where nothing more important is already written.
  const shapes = [tight, wrap(context, name, spill, maxLines)];
  if (tight.cut) {
    const longest = Math.max(...name.split(/\s+/).map((word) => context.measureText(word).width));
    const fits = Math.floor((h - countBlock) / lineHeight);
    const room = Math.max(maxLines, Math.min(MAX_NAME_LINES, fits));
    shapes.push(wrap(context, name, Math.min(spill, Math.max(inside, longest)), room));
  }
  const whole = shapes.filter((shape) => !shape.cut);
  whole.sort((a, b) => a.lines.length - b.lines.length);
  let chosen: ReturnType<typeof layout> | null = null;
  for (const shape of whole) {
    const spot = layout(shape.lines);
    if (!grid.place(spot.left, spot.top - 2, spot.right, spot.bottom + 2)) continue;
    chosen = spot;
    break;
  }
  if (!chosen) {
    if (ALWAYS_NAMED > w) return;
    chosen = layout(tight.lines);
    grid.place(chosen.left, chosen.top - 2, chosen.right, chosen.bottom + 2, true);
  }

  context.textAlign = "center";
  context.lineWidth = 4;
  context.strokeStyle = palette.background;
  context.fillStyle = palette.foreground;
  let y = chosen.top + size;
  for (const line of chosen.lines) {
    context.globalAlpha = alpha * 0.9;
    context.strokeText(line, chosen.cx, y);
    context.globalAlpha = alpha;
    context.fillText(line, chosen.cx, y);
    y += lineHeight;
  }
  if (count) {
    context.font = `400 ${countSize}px ${palette.font}`;
    context.fillStyle = palette.muted;
    y += countSize * 0.35 - lineHeight + size;
    context.globalAlpha = alpha * 0.9;
    context.strokeText(count, chosen.cx, y);
    context.globalAlpha = alpha;
    context.fillText(count, chosen.cx, y);
  }
}

function headerName(
  context: CanvasRenderingContext2D,
  scene: Scene,
  name: string,
  colour: string,
  x0: number,
  y0: number,
  w: number,
  h: number,
  alpha: number,
) {
  const { frame, palette, grid, reserved } = scene;
  const size = 11;
  let left = Math.max(x0, 0) + 8;
  let right = Math.min(x0 + w, frame.width) - 8;
  const baseline = Math.min(Math.max(y0, 0) + 17, y0 + h - 6);
  // The canvas's own chrome sits over it, and a header under the layout switch names a unit
  // nobody can read: a box over the header's start pushes it past the box, one further along
  // makes it end before the box.
  for (const [bx0, by0, bx1, by1] of reserved) {
    if (by0 > baseline + 4 || baseline - size - 3 > by1 || bx0 > right || left > bx1) continue;
    if (left + 48 > bx0) left = bx1 + 8;
    else right = bx0 - 8;
  }
  const room = right - left;
  if (room < 48 || baseline < 12) return;
  context.font = `600 ${size}px ${palette.font}`;
  const text = fit(context, name.toUpperCase(), room - 14);
  const width = context.measureText(text).width;
  grid.place(left - 3, baseline - size - 3, left + 14 + width + 3, baseline + 4, true);
  // A plate of the card's own colour behind it, so the header reads over lines and discs.
  context.globalAlpha = alpha * 0.9;
  context.fillStyle = palette.background;
  context.fillRect(left - 3, baseline - size - 3, width + 20, size + 7);
  context.globalAlpha = alpha;
  context.fillStyle = colour;
  context.fillRect(left, baseline - 8, 7, 7);
  context.fillStyle = palette.foreground;
  context.textAlign = "left";
  context.fillText(text, left + 13, baseline);
}

/** Break a name into at most `lines` lines of `maxWidth`, the last one cut with an ellipsis;
 *  `cut` says whether any of it had to go. */
function wrap(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  lines: number,
): { lines: string[]; cut: boolean } {
  const words = text.split(/\s+/).filter(Boolean);
  const out: string[] = [];
  let current = "";
  for (let index = 0; index < words.length; index += 1) {
    const next = current ? `${current} ${words[index]}` : words[index];
    if (!current || context.measureText(next).width <= maxWidth) {
      current = next;
      continue;
    }
    out.push(current);
    if (out.length === lines - 1) {
      current = words.slice(index).join(" ");
      break;
    }
    current = words[index];
  }
  if (current) out.push(current);
  const fitted = out.map((line) => fit(context, line, maxWidth));
  return { lines: fitted, cut: fitted.some((line, index) => line !== out[index]) };
}

/** `value` clamped to `[low, high]`, unless the clamp would take it outside `[from, to]`. */
function within(value: number, low: number, high: number, from: number, to: number) {
  const clamped = Math.min(Math.max(value, low), high);
  return clamped >= from && to >= clamped ? clamped : value;
}

/** The longest start of `text` that fits `maxWidth` with an ellipsis, or the text itself. */
function fit(context: CanvasRenderingContext2D, text: string, maxWidth: number) {
  if (context.measureText(text).width <= maxWidth) return text;
  let low = 0;
  let high = text.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (context.measureText(`${text.slice(0, middle)}…`).width <= maxWidth) low = middle;
    else high = middle - 1;
  }
  return low > 0 ? `${text.slice(0, low).trimEnd()}…` : "…";
}

/** The bands of the curriculum, with the depth written in the margin. Without them the
 *  rows are just rows; with them the picture says "this is an order". Band extents are
 *  measured from the bodies rather than from the layout, so a dragged node — or a frame
 *  mid-animation — keeps its rule where the eye expects it. */
function drawLevels(context: CanvasRenderingContext2D, scene: Scene) {
  const { model, bodies, view, palette } = scene;
  if (model.levelCount < 2) return;

  let minX = Infinity;
  let maxX = -Infinity;
  const top = new Array<number>(model.levelCount).fill(Infinity);
  const bottom = new Array<number>(model.levelCount).fill(-Infinity);
  for (let index = 0; index < bodies.length; index += 1) {
    const body = bodies[index];
    if (!body) continue;
    if (body.x < minX) minX = body.x;
    if (body.x > maxX) maxX = body.x;
    const level = model.levels[index];
    if (body.y < top[level]) top[level] = body.y;
    if (body.y > bottom[level]) bottom[level] = body.y;
  }
  if (!Number.isFinite(minX)) return;

  const left = minX - 52;
  const right = maxX + 34;
  context.strokeStyle = palette.border;
  context.lineWidth = 1 / view.scale;
  context.globalAlpha = 0.55;
  context.beginPath();
  for (let level = 1; level < model.levelCount; level += 1) {
    if (!Number.isFinite(bottom[level - 1]) || !Number.isFinite(top[level])) continue;
    const y = (bottom[level - 1] + top[level]) / 2;
    context.moveTo(left, y);
    context.lineTo(right, y);
  }
  context.stroke();

  context.globalAlpha = 0.8;
  context.fillStyle = palette.muted;
  context.font = `600 ${11 / view.scale}px ${palette.font}`;
  context.textAlign = "right";
  context.textBaseline = "middle";
  for (let level = 0; level < model.levelCount; level += 1) {
    if (!Number.isFinite(top[level])) continue;
    context.fillText(`N${level}`, left - 10, (top[level] + bottom[level]) / 2);
  }
  context.globalAlpha = 1;
}

/** The whole map in a corner, with a box where the camera is: the units as their regions, or
 *  the concepts as dots in the order view. It is what a zoomed-in map always loses — where
 *  you are in it. */
export function drawMinimap(
  context: CanvasRenderingContext2D,
  scene: Scene,
  box: { x: number; y: number; width: number; height: number },
) {
  const { bodies, model, graph, view, frame, palette, regions } = scene;
  const units = scene.mode === "force" && regions.length > 0;
  if (!units && bodies.length === 0) return;

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  if (units) {
    for (const region of regions) {
      minX = Math.min(minX, region.x);
      minY = Math.min(minY, region.y);
      maxX = Math.max(maxX, region.x + region.width);
      maxY = Math.max(maxY, region.y + region.height);
    }
  } else {
    for (const body of bodies) {
      if (body.x < minX) minX = body.x;
      if (body.y < minY) minY = body.y;
      if (body.x > maxX) maxX = body.x;
      if (body.y > maxY) maxY = body.y;
    }
  }
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const scale = Math.min((box.width - 8) / spanX, (box.height - 8) / spanY);
  const originX = box.x + box.width / 2 - ((minX + maxX) / 2) * scale;
  const originY = box.y + box.height / 2 - ((minY + maxY) / 2) * scale;

  const ratio = Math.min(2, window.devicePixelRatio || 1);
  context.save();
  context.setTransform(ratio, 0, 0, ratio, 0, 0);

  context.globalAlpha = 0.94;
  context.fillStyle = palette.background;
  context.strokeStyle = palette.border;
  context.lineWidth = 1;
  context.fillRect(box.x, box.y, box.width, box.height);
  context.strokeRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1);

  if (units) {
    context.globalAlpha = 0.5;
    for (const region of regions) {
      context.fillStyle = model.domainColours[region.group] ?? palette.muted;
      context.fillRect(
        originX + region.x * scale,
        originY + region.y * scale,
        Math.max(1, region.width * scale),
        Math.max(1, region.height * scale),
      );
    }
  } else {
    context.globalAlpha = 0.85;
    const step = Math.max(1, Math.floor(bodies.length / 4000));
    for (let index = 0; index < bodies.length; index += step) {
      const body = bodies[index];
      const group = graph.nodes[index]?.[1] ?? 0;
      context.fillStyle = model.domainColours[group] ?? palette.muted;
      context.fillRect(originX + body.x * scale - 1, originY + body.y * scale - 1, 2, 2);
    }
  }

  // The viewport in world units, mapped through the same transform.
  const halfW = frame.width / 2 / view.scale;
  const halfH = frame.height / 2 / view.scale;
  const centreX = -view.x / view.scale;
  const centreY = -view.y / view.scale;
  context.globalAlpha = 1;
  context.strokeStyle = palette.accent;
  context.lineWidth = 1.25;
  context.beginPath();
  context.rect(box.x, box.y, box.width, box.height);
  context.clip();
  context.strokeRect(
    originX + (centreX - halfW) * scale,
    originY + (centreY - halfH) * scale,
    halfW * 2 * scale,
    halfH * 2 * scale,
  );
  context.restore();
}
