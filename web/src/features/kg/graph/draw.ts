import type { GraphView } from "@/lib/types";
import type { Body, Frame, LayoutMode } from "./layout";
import type { GraphModel } from "./model";

export interface Palette {
  foreground: string;
  muted: string;
  border: string;
  background: string;
  accent: string;
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
  focused: number;
  highlight?: Set<string>;
  hiddenRelations?: Set<number>;
}

const LABEL_SCALE = 1.05;
const CURVE = 0.14;
const ARROW = 7;
const DIM = 0.12;

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
    accent: read("--primary", "#3b82f6"),
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

  if (hulls && scene.mode === "force") drawHulls(context, scene, focus);
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
    const dimmed = (focus >= 0 && !isFocus && !isNear) || !isMarked;

    context.globalAlpha = dimmed ? DIM : 1;
    context.fillStyle = model.domainColours[group] ?? palette.muted;
    context.beginPath();
    context.arc(body.x, body.y, radius, 0, Math.PI * 2);
    context.fill();

    // A non-taggable concept is in the graph for its relations only: nothing is ever
    // labelled with it. Drawn hollow, so it reads as structure rather than as a target.
    if (nonTaggable) {
      context.globalAlpha = dimmed ? DIM : 1;
      context.fillStyle = palette.background;
      context.beginPath();
      context.arc(body.x, body.y, Math.max(1.5, radius - 2.4), 0, Math.PI * 2);
      context.fill();
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
    context.font = `${strong ? 600 : 400} ${11 / scale}px ui-sans-serif, system-ui`;
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
  const showArrows = arrows && scale > 0.55;

  // Edges are batched per relation type: one path per colour instead of a stroke per
  // edge. The focused node's own edges are held back and drawn on top, opaque.
  const focused: [number, number, number][] = [];

  for (let relation = 0; relation < graph.relations.length; relation += 1) {
    if (hidden?.has(relation)) continue;
    context.strokeStyle = model.relationColours[relation] ?? palette.border;
    context.globalAlpha = focus >= 0 ? 0.08 : 0.45;
    context.lineWidth = 1.1 / scale;
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
      context.globalAlpha = 0.45;
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

/** A soft blob behind each domain. Not a convex hull: a hull around an outlier swallows
 *  half the canvas. Overlapping discs, one per node, union into a shape that follows
 *  where the domain actually is and degrades gracefully when it is scattered. */
function drawHulls(context: CanvasRenderingContext2D, scene: Scene, focus: number) {
  const { graph, model, bodies, view } = scene;
  if (focus >= 0) return;

  const members = new Map<number, number[]>();
  graph.nodes.forEach(([, group], index) => {
    if (!members.has(group)) members.set(group, []);
    members.get(group)!.push(index);
  });

  // The discs grow as you zoom out, so a blob keeps roughly the same weight on screen
  // instead of dissolving into the background at low scale.
  const radius = 34 / Math.max(0.6, view.scale) + 18;

  context.globalAlpha = 0.07;
  for (const [group, nodes] of members) {
    if (nodes.length < 3) continue;
    context.fillStyle = model.domainColours[group] ?? "transparent";
    context.beginPath();
    for (const node of nodes) {
      const body = bodies[node];
      if (!body) continue;
      // moveTo the arc's own start point: otherwise each disc drags a chord in from
      // wherever the previous one ended, and the union fills with stray wedges.
      context.moveTo(body.x + radius, body.y);
      context.arc(body.x, body.y, radius, 0, Math.PI * 2);
    }
    context.fill();
  }
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
  context.font = `600 ${11 / view.scale}px ui-sans-serif, system-ui`;
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
    context.fillRect(originX + body.x * scale - 0.75, originY + body.y * scale - 0.75, 1.5, 1.5);
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
