import { TONE_VAR } from "@/lib/status";
import type { GraphView } from "@/lib/types";
import type { Body, Frame, LayoutMode } from "./layout";
import type { GraphModel } from "./model";

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
  hulls: boolean;
  selected: number;
  picked?: Set<number>;
  focused: number;
  highlight?: Set<string>;
  hiddenRelations?: Set<number>;
  /** Node indices the course has already covered. `undefined` — not an empty set — means
   *  no curriculum is in force, and everything keeps its domain colour. An EMPTY set is a
   *  curriculum that was deliberately emptied, which is a different statement. */
  curriculum?: Set<number>;
  /** Covered nothing, but every prerequisite covered: what can be taught next. */
  frontier?: Set<number>;
}

// The same calculation the generator already performs for every commission — assumed_known
// / target / forbidden — drawn. Covered in verdigris, the frontier in ochre, what has not
// been taught dimmed.
//
// Outside the curriculum view the colour stays the domain's: there, what you read is what
// each concept is ABOUT, not the order it is taught in.
function nodeFill(scene: Scene, index: number, group: number): string {
  const { palette, model } = scene;
  if (scene.mode !== "curriculum" || !scene.curriculum) {
    return model.domainColours[group] ?? palette.muted;
  }
  if (scene.frontier?.has(index)) return palette.attention;
  if (scene.curriculum.has(index)) return palette.settled;
  return palette.ahead;
}

interface HullLabel {
  text: string;
  x: number;
  y: number;
  colour: string;
}

const LABEL_SCALE = 1.05;
const CURVE = 0.14;
const ARROW = 7;
const DIM = 0.12;
const FONT_SANS = '"IBM Plex Sans Variable", ui-sans-serif, system-ui';
const FONT_DISPLAY = '"Archivo Variable", "Archivo", ui-sans-serif, system-ui';

export function radiusOf(degree: number) {
  return 4 + Math.min(9, Math.sqrt(degree) * 2.2);
}

export function readPalette(): Palette {
  const styles = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) =>
    styles.getPropertyValue(name).trim() || fallback;
  return {
    foreground: read("--foreground", "#111"),
    muted: read("--muted-foreground", "#888"),
    border: read("--border", "#ddd"),
    background: read("--card", "#fff"),
    accent: read("--primary", "#6217A3"),
    settled: read(TONE_VAR.settled, "#1C7760"),
    attention: read(TONE_VAR.attention, "#9A6100"),
    ahead: read(TONE_VAR.muted, "#888"),
  };
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

export function draw(context: CanvasRenderingContext2D, scene: Scene) {
  const { graph, model, bodies, view, frame, palette, labels, arrows, hulls } = scene;
  const { width, height } = frame;
  if (width === 0 || height === 0) return;

  const ratio = Math.min(2, window.devicePixelRatio || 1);
  const { scale } = view;

  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  context.save();
  context.translate(width / 2 + view.x, height / 2 + view.y);
  context.scale(scale, scale);

  const focus = scene.focused >= 0 ? scene.focused : scene.selected;
  const near = focus >= 0 ? model.adjacency.get(focus) : undefined;

  const hullLabels =
    hulls && scene.mode === "force" ? drawHulls(context, scene, focus) : [];
  if (scene.mode === "force") drawParkedLane(context, scene);
  if (scene.mode === "curriculum") drawLevels(context, scene);

  drawEdges(context, scene, focus, arrows);

  const placed: [number, number, number, number][] = [];
  const pending: {
    text: string;
    x: number;
    y: number;
    strong: boolean;
    dim: boolean;
    weight: number;
  }[] = [];
  const showAll = labels === "all" || (labels === "auto" && scale > LABEL_SCALE);

  context.globalAlpha = 1;
  for (let index = 0; index < graph.nodes.length; index += 1) {
    const body = bodies[index];
    if (!body) continue;
    const [name, group, nonTaggable] = graph.nodes[index];
    const radius = radiusOf(model.degrees[index] ?? 0);
    const isFocus = index === focus;
    const isNear = near?.has(index) ?? false;
    const isMarked = scene.highlight ? scene.highlight.has(name) : true;
    const isPicked = scene.picked?.has(index) ?? false;
    const dimmed = !isPicked && ((focus >= 0 && !isFocus && !isNear) || !isMarked);

    context.globalAlpha = dimmed ? DIM : 1;
    context.fillStyle = isPicked ? palette.accent : nodeFill(scene, index, group);
    context.beginPath();
    context.arc(body.x, body.y, radius, 0, Math.PI * 2);
    context.fill();

    // A non-taggable concept is in the graph for its relations only: nothing is ever
    // labelled with it. Drawn hollow and slightly faded, so it reads as structure
    // rather than as a target — the filled, taggable nodes are the ones that lead.
    if (nonTaggable) {
      context.globalAlpha = dimmed ? DIM : 0.9;
      context.fillStyle = palette.background;
      context.beginPath();
      context.arc(body.x, body.y, Math.max(1.5, radius - 1.7), 0, Math.PI * 2);
      context.fill();
    }

    if (isPicked) {
      context.globalAlpha = 1;
      context.strokeStyle = palette.accent;
      context.lineWidth = 2 / scale;
      context.beginPath();
      context.arc(body.x, body.y, radius + 3, 0, Math.PI * 2);
      context.stroke();
    }

    if (index === scene.selected) {
      context.globalAlpha = 1;
      context.strokeStyle = palette.foreground;
      context.lineWidth = 2.5 / scale;
      context.beginPath();
      context.arc(body.x, body.y, radius + 4, 0, Math.PI * 2);
      context.stroke();
    }

    if (
      labels !== "none" &&
      (isFocus ||
        isNear ||
        isPicked ||
        index === scene.selected ||
        showAll ||
        (model.hubs.has(index) && !dimmed) ||
        (scene.highlight && scene.highlight.size <= 14 && isMarked))
    ) {
      pending.push({
        text: name,
        x: body.x,
        y: body.y - radius - 4 / scale,
        strong: isFocus || index === scene.selected,
        dim: dimmed,
        weight: model.degrees[index] ?? 0,
      });
    }
  }

  drawHullLabels(context, scene, hullLabels, placed);

  // Labels last and grouped by weight: `context.font` is a parsed string, and setting
  // it per node was most of the per-frame cost at this node count. The ones the user
  // asked for (focus, selection) are drawn first and always; the rest give way to
  // whatever is already on the canvas instead of overprinting it.
  context.textAlign = "center";
  context.textBaseline = "alphabetic";
  const lineHeight = 13 / scale;

  const paint = (strong: boolean) => {
    const chosen = pending
      .filter((label) => label.strong === strong)
      .sort((a, b) => b.weight - a.weight);
    if (chosen.length === 0) return;
    context.font = `${strong ? 600 : 400} ${11 / scale}px ${FONT_SANS}`;
    for (const label of chosen) {
      const halfWidth = context.measureText(label.text).width / 2;
      const box: [number, number, number, number] = [
        label.x - halfWidth,
        label.y - lineHeight,
        label.x + halfWidth,
        label.y + lineHeight * 0.3,
      ];
      const collides = placed.some(
        (r) => box[0] < r[2] && box[2] > r[0] && box[1] < r[3] && box[3] > r[1],
      );
      if (!strong && collides) continue;
      placed.push(box);
      context.globalAlpha = label.dim ? 0.3 : 1;
      // A halo under the text, so a label crossing an edge stays readable without
      // having to hide the edge.
      context.lineWidth = 3 / scale;
      context.strokeStyle = palette.background;
      context.lineJoin = "round";
      context.strokeText(label.text, label.x, label.y);
      context.fillStyle = strong ? palette.foreground : palette.muted;
      context.fillText(label.text, label.x, label.y);
    }
  };
  paint(true);
  paint(false);

  context.globalAlpha = 1;
  context.restore();
}

function drawEdges(
  context: CanvasRenderingContext2D,
  scene: Scene,
  focus: number,
  arrows: boolean,
) {
  const { graph, model, bodies, view, palette } = scene;
  const { scale } = view;
  const hidden = scene.hiddenRelations;

  // Edge ink is budgeted by how many edges there are: the alpha that reads as "a few
  // lines" on a 180-edge graph reads as a grey wash on a 500-edge one, and the wash is
  // what buries the nodes. Same for the arrowheads — 485 of them at a zoom where each is
  // four pixels wide is texture, not direction, so they wait until the zoom can show one.
  const density = Math.min(1, graph.links.length / 260);
  const restAlpha = 0.42 - density * 0.17;
  const showArrows = arrows && scale > 0.55 + density * 0.35;

  // Edges are batched per relation type: one path per colour instead of a stroke per
  // edge. The focused node's own edges are held back and drawn on top, opaque.
  const focused: [number, number, number][] = [];

  // Ink follows meaning: the prerequisite relation is the one the whole pedagogy runs
  // on, so it gets more ink than the rest; the catch-all gets less. In the curriculum
  // view — which IS the prerequisite order — the relations that do not order anything
  // fade to a whisper instead of crossing every band as spaghetti.
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

  for (let relation = 0; relation < graph.relations.length; relation += 1) {
    if (hidden?.has(relation)) continue;
    const ink = inkOf(relation);
    context.strokeStyle = model.relationColours[relation] ?? palette.border;
    context.globalAlpha = focus >= 0 ? 0.07 : ink.alpha;
    context.lineWidth = ink.width / scale;
    context.beginPath();
    let drawn = 0;
    for (const link of graph.links) {
      if (link[2] !== relation) continue;
      const [source, target] = link;
      if (focus >= 0 && (source === focus || target === focus)) {
        focused.push(link);
        continue;
      }
      const a = bodies[source];
      const b = bodies[target];
      if (!a || !b) continue;
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
      context.fillStyle = model.relationColours[relation] ?? palette.border;
      context.globalAlpha = inkOf(relation).alpha;
      for (const [source, target, kind] of graph.links) {
        if (kind !== relation) continue;
        arrowhead(context, scene, source, target);
      }
    }
  }

  for (const [source, target, relation] of focused) {
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
    if (arrows && graph.relations[relation].directed) {
      context.fillStyle = model.relationColours[relation] ?? palette.foreground;
      arrowhead(context, scene, source, target);
    }
  }
  context.globalAlpha = 1;
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
  const radius = radiusOf(scene.model.degrees[target] ?? 0);
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
  context.lineTo(
    tipX - Math.cos(angle - 0.42) * size,
    tipY - Math.sin(angle - 0.42) * size,
  );
  context.lineTo(
    tipX - Math.cos(angle + 0.42) * size,
    tipY - Math.sin(angle + 0.42) * size,
  );
  context.closePath();
  context.fill();
}

/**
 * A soft region behind each domain, with its name on it.
 *
 * Not a convex hull: a hull around an outlier swallows half the canvas. Overlapping
 * discs, one per node, union into a shape that follows where the domain actually is and
 * degrades gracefully when it is scattered.
 *
 * Two things make it a map rather than fog. Parked nodes are excluded, so a domain's
 * blob does not stretch across the canvas to reach its own isolated members. And the
 * domain is NAMED, at the centre of its members: an unlabelled tint is decoration, and
 * seven of them in similar colours is worse than none — you had to match the blob
 * against a legend somewhere else on the page to learn anything from it.
 *
 * Only the blob is painted here, because it is a background. The names are returned for
 * `drawHullLabels` to paint over the nodes.
 */
function drawHulls(
  context: CanvasRenderingContext2D,
  scene: Scene,
  focus: number,
): HullLabel[] {
  const { graph, model, bodies, view, palette } = scene;
  if (focus >= 0) return [];

  // The discs grow as you zoom out, so a blob keeps roughly the same weight on screen
  // instead of dissolving into the background at low scale. Kept tight and faint on
  // purpose: the tint is ambient signage behind the drawing, never a layer over it.
  const radius = 20 / Math.max(0.6, view.scale) + 13;
  const labels: HullLabel[] = [];

  for (let group = 0; group < model.groupCount; group += 1) {
    const nodes = model.domainMembers[group];
    if (!nodes || nodes.length < 3) continue;

    context.globalAlpha = 0.055;
    context.fillStyle = model.domainColours[group] ?? "transparent";
    context.beginPath();
    let sumX = 0;
    let sumY = 0;
    let seen = 0;
    // Parked members are skipped inline rather than filtered out: this runs every frame,
    // and a `.filter()` per domain is one array per domain per frame.
    for (const node of nodes) {
      const body = bodies[node];
      if (!body || body.parked) continue;
      // moveTo the arc's own start point: otherwise each disc drags a chord in from
      // wherever the previous one ended, and the union fills with stray wedges.
      context.moveTo(body.x + radius, body.y);
      context.arc(body.x, body.y, radius, 0, Math.PI * 2);
      sumX += body.x;
      sumY += body.y;
      seen += 1;
    }
    context.fill();

    const name = graph.groups[group]?.name;
    if (seen > 0 && name) {
      labels.push({
        text: name.toUpperCase(),
        x: sumX / seen,
        y: sumY / seen,
        colour: model.domainColours[group] ?? palette.muted,
      });
    }
  }

  context.globalAlpha = 1;
  return labels;
}

/**
 * The domain names, over every blob and over the nodes: a name that a node can cover is
 * a name you cannot read, and the blob it belongs to is exactly where the nodes are.
 *
 * The boxes it claims are pushed into the label grid, so the concept labels that give
 * way to each other give way to these too instead of overprinting them.
 */
function drawHullLabels(
  context: CanvasRenderingContext2D,
  scene: Scene,
  labels: HullLabel[],
  placed: [number, number, number, number][],
) {
  if (labels.length === 0) return;
  const { view, palette } = scene;
  const size = Math.min(17, 11.5 / view.scale);

  // Ambient signage, not headline: the display face with tracking, at reduced weight
  // and alpha, so the names locate the neighbourhoods without shouting over them.
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.font = `600 ${size}px ${FONT_DISPLAY}`;
  const spaced = context as CanvasRenderingContext2D & { letterSpacing?: string };
  if (spaced.letterSpacing !== undefined) {
    spaced.letterSpacing = `${(size * 0.14).toFixed(2)}px`;
  }
  context.lineJoin = "round";
  for (const label of labels) {
    const text = label.text;
    const halfWidth = context.measureText(text).width / 2;
    // Two neighbourhoods can meet exactly where both their names want to sit; the
    // second one steps down instead of overprinting the first.
    let y = label.y;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const box: [number, number, number, number] = [
        label.x - halfWidth,
        y - size * 0.6,
        label.x + halfWidth,
        y + size * 0.6,
      ];
      const collides = placed.some(
        (r) => box[0] < r[2] && box[2] > r[0] && box[1] < r[3] && box[3] > r[1],
      );
      if (!collides) break;
      y += size * 1.35;
    }
    placed.push([label.x - halfWidth, y - size * 0.6, label.x + halfWidth, y + size * 0.6]);
    // A wider, more opaque halo than the concept labels get: this one is over the nodes
    // and their edges now, not over an empty tint, so it has to cut its own hole.
    context.globalAlpha = 0.6;
    context.lineWidth = 4.5 / view.scale;
    context.strokeStyle = palette.background;
    context.strokeText(text, label.x, y);
    context.globalAlpha = 0.62;
    context.fillStyle = label.colour;
    context.fillText(text, label.x, y);
  }
  if (spaced.letterSpacing !== undefined) spaced.letterSpacing = "0px";
  context.globalAlpha = 1;
}

/**
 * The lane the isolated concepts were parked in, told apart from the graph.
 *
 * Without the rule and the caption the column reads as a part of the layout that went
 * wrong. With them it reads as what it is: the concepts no relation mentions, which is
 * the single most actionable thing this view can point at — every one of them is a
 * missing edge.
 */
function drawParkedLane(context: CanvasRenderingContext2D, scene: Scene) {
  const { model, bodies, view, palette } = scene;
  if (model.isolated.length === 0) return;

  let minX = Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const node of model.isolated) {
    const body = bodies[node];
    if (!body) continue;
    if (body.x < minX) minX = body.x;
    if (body.y < minY) minY = body.y;
    if (body.y > maxY) maxY = body.y;
  }
  if (!Number.isFinite(minX)) return;

  const rule = minX - 26;
  context.strokeStyle = palette.border;
  context.lineWidth = 1 / view.scale;
  context.globalAlpha = 0.7;
  context.beginPath();
  context.moveTo(rule, minY - 22);
  context.lineTo(rule, maxY + 22);
  context.stroke();

  // Horizontal, above the lane: rotated text next to one or two dots read as a layout
  // accident, not as a caption.
  context.globalAlpha = 0.75;
  context.fillStyle = palette.muted;
  context.font = `600 ${Math.min(16, 10 / view.scale)}px ${FONT_SANS}`;
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
  const caption =
    model.isolated.length === 1 ? "1 sin relaciones" : `${model.isolated.length} sin relaciones`;
  context.fillText(caption, rule, minY - 30);
  context.globalAlpha = 1;
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
  context.font = `600 ${11 / view.scale}px ${FONT_SANS}`;
  context.textAlign = "right";
  context.textBaseline = "middle";
  for (let level = 0; level < model.levelCount; level += 1) {
    if (!Number.isFinite(top[level])) continue;
    context.fillText(`N${level}`, left - 10, (top[level] + bottom[level]) / 2);
  }
  context.globalAlpha = 1;
}

/** The whole graph in a corner, with a box where the camera is. It is the cheapest fix
 *  for the one thing a zoomed-in force layout always loses: where you are in it. */
export function drawMinimap(
  context: CanvasRenderingContext2D,
  scene: Scene,
  box: { x: number; y: number; width: number; height: number },
) {
  const { bodies, model, graph, view, frame, palette } = scene;
  if (bodies.length === 0) return;

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const body of bodies) {
    if (body.x < minX) minX = body.x;
    if (body.y < minY) minY = body.y;
    if (body.x > maxX) maxX = body.x;
    if (body.y > maxY) maxY = body.y;
  }
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const scale = Math.min((box.width - 8) / spanX, (box.height - 8) / spanY);
  const originX = box.x + box.width / 2 - ((minX + maxX) / 2) * scale;
  const originY = box.y + box.height / 2 - ((minY + maxY) / 2) * scale;

  context.save();
  context.setTransform(
    Math.min(2, window.devicePixelRatio || 1),
    0,
    0,
    Math.min(2, window.devicePixelRatio || 1),
    0,
    0,
  );

  context.globalAlpha = 0.92;
  context.fillStyle = palette.background;
  context.strokeStyle = palette.border;
  context.lineWidth = 1;
  roundRect(context, box.x, box.y, box.width, box.height, 6);
  context.fill();
  context.stroke();

  context.globalAlpha = 0.85;
  for (let index = 0; index < bodies.length; index += 1) {
    const body = bodies[index];
    const group = graph.nodes[index]?.[1] ?? 0;
    context.fillStyle = model.domainColours[group] ?? palette.muted;
    context.fillRect(originX + body.x * scale - 1, originY + body.y * scale - 1, 2, 2);
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
  context.rect(
    originX + (centreX - halfW) * scale,
    originY + (centreY - halfH) * scale,
    halfW * 2 * scale,
    halfH * 2 * scale,
  );
  context.save();
  roundRect(context, box.x, box.y, box.width, box.height, 6);
  context.clip();
  context.stroke();
  context.restore();

  context.restore();
}

function roundRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}
