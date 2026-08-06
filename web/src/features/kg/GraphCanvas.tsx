import { Maximize2, RotateCw, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { domainColour } from "@/lib/format";
import type { GraphView } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Force-directed layout on a canvas, drawn by hand.
 *
 * 118 concepts and ~180 edges do not need a physics library: a Fruchterman-Reingold
 * relaxation is a few dozen lines, and owning the render loop is what lets the graph
 * share selection with the table beside it and follow the app's own theme.
 *
 * Owning the loop also means owning when it stops. Three rules keep it cheap:
 * the frame is only requested while the layout is hot or something changed; nothing
 * inside a frame reads the DOM (size comes from a ResizeObserver, colours from a
 * cached palette — both used to force a reflow on every single frame); and the
 * props the drawing depends on live in refs, so a keystroke in the search box
 * repaints instead of tearing down and restarting the animation.
 */

interface Body {
  x: number;
  y: number;
  dx: number;
  dy: number;
  pinned: boolean;
}

interface Props {
  graph: GraphView;
  selected: string | null;
  onSelect: (concept: string | null) => void;
  highlight?: Set<string>;
  hiddenRelations?: Set<number>;
  className?: string;
}

const MIN_SCALE = 0.2;
const MAX_SCALE = 4;
const SETTLED = 0.4;
const COOLING = 0.975;
const PADDING = 44;
const LABEL_SCALE = 1.1;
const HUB_LABELS = 14;

// Fruchterman-Reingold constants, measured against this graph (118 concepts, 182
// edges) rather than guessed. Unbounded, the relaxation spread to ~5000 units and the
// camera had to zoom out to 0.2 to show it — the "graph is tiny and half off-screen"
// this replaces. Bounding it to the canvas and tuning these two makes the layout fill
// the frame with a single node touching the border: REPULSION sets the edge length
// (~78 px), GRAVITY keeps the periphery off the boundary.
const REPULSION = 0.45;
const GRAVITY = 0.5;

function readPalette() {
  const styles = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) =>
    styles.getPropertyValue(name).trim() || fallback;
  return {
    foreground: read("--foreground", "#111"),
    muted: read("--muted-foreground", "#888"),
    border: read("--border", "#ddd"),
    background: read("--card", "#fff"),
  };
}

function radiusOf(degree: number) {
  return 4 + Math.min(9, Math.sqrt(degree) * 2.2);
}

export function GraphCanvas({
  graph,
  selected,
  onSelect,
  highlight,
  hiddenRelations,
  className,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const bodies = useRef<Body[]>([]);
  const view = useRef({ x: 0, y: 0, scale: 1 });
  const temperature = useRef(0);
  const size = useRef({ width: 0, height: 0 });
  const palette = useRef(readPalette());
  const dirty = useRef(true);
  const frame = useRef<number | null>(null);
  const pendingFit = useRef(true);
  const loopRef = useRef<() => void>(() => {});

  const pointer = useRef<{
    mode: "none" | "pan" | "node";
    index: number;
    x: number;
    y: number;
    moved: number;
  }>({ mode: "none", index: -1, x: 0, y: 0, moved: 0 });
  const [hovered, setHovered] = useState<number | null>(null);
  const hoveredRef = useRef<number | null>(null);
  hoveredRef.current = hovered;

  const nodeCount = graph.nodes.length;

  const model = useMemo(() => {
    const degrees = new Array<number>(nodeCount).fill(0);
    const adjacency = new Map<number, Set<number>>();
    for (const [source, target] of graph.links) {
      degrees[source] += 1;
      degrees[target] += 1;
      if (!adjacency.has(source)) adjacency.set(source, new Set());
      if (!adjacency.has(target)) adjacency.set(target, new Set());
      adjacency.get(source)!.add(target);
      adjacency.get(target)!.add(source);
    }
    const nameIndex = new Map<string, number>();
    graph.nodes.forEach(([name], index) => nameIndex.set(name, index));
    // One colour string per domain, built once: `domainColour` inside the draw loop
    // meant 118 template strings a frame for six distinct values.
    const colours = graph.groups.map((_, index) => domainColour(index, graph.groups.length));
    // A graph with no labels is a constellation. The hubs get theirs permanently — few
    // enough not to collide, and they are what you navigate by.
    const hubs = new Set(
      degrees
        .map((degree, index) => [degree, index])
        .sort((a, b) => b[0] - a[0])
        .slice(0, HUB_LABELS)
        .filter(([degree]) => degree > 1)
        .map(([, index]) => index),
    );
    return { degrees, adjacency, nameIndex, colours, hubs };
  }, [graph, nodeCount]);

  const modelRef = useRef(model);
  modelRef.current = model;
  const graphRef = useRef(graph);
  graphRef.current = graph;
  const viewProps = useRef({ selected, highlight, hiddenRelations });
  viewProps.current = { selected, highlight, hiddenRelations };

  const wake = useCallback(() => {
    if (frame.current === null) frame.current = requestAnimationFrame(() => loopRef.current());
  }, []);

  const repaint = useCallback(() => {
    dirty.current = true;
    wake();
  }, [wake]);

  const reheat = useCallback(
    (fraction = 1) => {
      const { width } = size.current;
      temperature.current = Math.max(2, (Math.max(400, width) / 10) * fraction);
      wake();
    },
    [wake],
  );

  const applyFit = useCallback(() => {
    const list = bodies.current;
    const { width, height } = size.current;
    if (list.length === 0 || width === 0 || height === 0) return false;

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const body of list) {
      if (body.x < minX) minX = body.x;
      if (body.y < minY) minY = body.y;
      if (body.x > maxX) maxX = body.x;
      if (body.y > maxY) maxY = body.y;
    }

    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const scale = Math.max(
      MIN_SCALE,
      Math.min(1.4, (width - PADDING * 2) / spanX, (height - PADDING * 2) / spanY),
    );
    const centreX = (minX + maxX) / 2;
    const centreY = (minY + maxY) / 2;
    view.current = { x: -centreX * scale, y: -centreY * scale, scale };
    return true;
  }, []);

  const fit = useCallback(() => {
    // An explicit "encuadrar" also gives the camera back to the layout: whatever the
    // relaxation does next stays in frame.
    pendingFit.current = true;
    applyFit();
    repaint();
  }, [applyFit, repaint]);

  /** Any manual pan, zoom or drag takes the camera away from the auto-fit for good. */
  const takeCamera = useCallback(() => {
    pendingFit.current = false;
  }, []);

  // Seed by domain: nodes of the same group start on the same arc, so the relaxation
  // starts from something already grouped and settles into readable clusters instead
  // of a ring that untangles itself on camera.
  useEffect(() => {
    const groupCount = Math.max(1, graph.groups.length);
    const halfWidth = Math.max(200, size.current.width / 2 - PADDING);
    const halfHeight = Math.max(150, size.current.height / 2 - PADDING);
    const seen = new Map<number, number>();
    bodies.current = graph.nodes.map(([, group]) => {
      const rank = seen.get(group) ?? 0;
      seen.set(group, rank + 1);
      const angle = (group / groupCount) * Math.PI * 2;
      const spread = 30 + Math.sqrt(rank + 1) * 18;
      return {
        x: Math.cos(angle) * halfWidth * 0.55 + Math.cos(rank * 2.4) * spread,
        y: Math.sin(angle) * halfHeight * 0.55 + Math.sin(rank * 2.4) * spread,
        dx: 0,
        dy: 0,
        pinned: false,
      };
    });
    pendingFit.current = true;
    reheat();
    repaint();
  }, [graph, reheat, repaint]);

  // Selection, search highlight and relation filters change what is drawn, never the
  // simulation: mark the canvas dirty and let the loop draw one more frame.
  useEffect(() => {
    repaint();
  }, [selected, highlight, hiddenRelations, hovered, repaint]);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const syncSize = () => {
      const rect = wrap.getBoundingClientRect();
      size.current = { width: rect.width, height: rect.height };
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      const width = Math.max(1, Math.round(rect.width * ratio));
      const height = Math.max(1, Math.round(rect.height * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      dirty.current = true;
    };

    const simulate = () => {
      const list = bodies.current;
      const n = list.length;
      if (n === 0) return;
      const halfWidth = Math.max(200, size.current.width / 2 - PADDING);
      const halfHeight = Math.max(150, size.current.height / 2 - PADDING);
      const k = REPULSION * Math.sqrt((halfWidth * 2 * halfHeight * 2) / n);
      const links = graphRef.current.links;
      const hidden = viewProps.current.hiddenRelations;

      for (const body of list) {
        body.dx = 0;
        body.dy = 0;
      }

      for (let i = 0; i < n; i += 1) {
        const a = list[i];
        for (let j = i + 1; j < n; j += 1) {
          const b = list[j];
          let deltaX = a.x - b.x;
          let deltaY = a.y - b.y;
          let distance = Math.hypot(deltaX, deltaY);
          if (distance < 0.01) {
            deltaX = Math.random() - 0.5;
            deltaY = Math.random() - 0.5;
            distance = 0.01;
          }
          const force = (k * k) / distance;
          const ux = (deltaX / distance) * force;
          const uy = (deltaY / distance) * force;
          a.dx += ux;
          a.dy += uy;
          b.dx -= ux;
          b.dy -= uy;
        }
      }

      for (const [source, target, relation] of links) {
        if (hidden?.has(relation)) continue;
        const a = list[source];
        const b = list[target];
        if (!a || !b) continue;
        const deltaX = a.x - b.x;
        const deltaY = a.y - b.y;
        const distance = Math.max(0.01, Math.hypot(deltaX, deltaY));
        const force = (distance * distance) / k;
        const ux = (deltaX / distance) * force;
        const uy = (deltaY / distance) * force;
        a.dx -= ux;
        a.dy -= uy;
        b.dx += ux;
        b.dy += uy;
      }

      // Gravity is elliptical, not round: pulling harder vertically than horizontally
      // makes the cloud take the shape of the canvas instead of a circle with two
      // empty margins. The clamp afterwards is classic FR — the frame is the world.
      const gravityY = GRAVITY * (halfWidth / halfHeight);
      const temp = temperature.current;
      for (const body of list) {
        if (body.pinned) continue;
        body.dx -= body.x * GRAVITY;
        body.dy -= body.y * gravityY;
        const magnitude = Math.max(0.01, Math.hypot(body.dx, body.dy));
        const move = Math.min(magnitude, temp);
        body.x = Math.max(-halfWidth, Math.min(halfWidth, body.x + (body.dx / magnitude) * move));
        body.y = Math.max(-halfHeight, Math.min(halfHeight, body.y + (body.dy / magnitude) * move));
      }
      temperature.current = temp * COOLING;
    };

    const draw = () => {
      const { width, height } = size.current;
      if (width === 0 || height === 0) return;

      const ratio = Math.min(2, window.devicePixelRatio || 1);
      const { foreground, muted, border, background } = palette.current;
      const { degrees, adjacency, nameIndex, colours, hubs } = modelRef.current;
      const { selected: current, highlight: marked, hiddenRelations: hidden } = viewProps.current;
      const { nodes, links } = graphRef.current;
      const list = bodies.current;
      const scale = view.current.scale;

      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      context.save();
      context.translate(width / 2 + view.current.x, height / 2 + view.current.y);
      context.scale(scale, scale);

      const selectedIndex = current ? (nameIndex.get(current) ?? -1) : -1;
      const focus = hoveredRef.current !== null ? hoveredRef.current : selectedIndex;
      const near = focus >= 0 ? adjacency.get(focus) : undefined;

      // Edges in two batched paths instead of a stroke per edge: one for the muted
      // background, one for the ones touching the focused node.
      context.lineWidth = 1 / scale;
      context.strokeStyle = border;
      context.globalAlpha = focus >= 0 ? 0.12 : 0.5;
      context.beginPath();
      for (const [source, target, relation] of links) {
        if (hidden?.has(relation)) continue;
        if (focus >= 0 && (source === focus || target === focus)) continue;
        const a = list[source];
        const b = list[target];
        if (!a || !b) continue;
        context.moveTo(a.x, a.y);
        context.lineTo(b.x, b.y);
      }
      context.stroke();

      if (focus >= 0) {
        context.strokeStyle = foreground;
        context.globalAlpha = 0.75;
        context.lineWidth = 1.4 / scale;
        context.beginPath();
        for (const [source, target, relation] of links) {
          if (hidden?.has(relation)) continue;
          if (source !== focus && target !== focus) continue;
          const a = list[source];
          const b = list[target];
          if (!a || !b) continue;
          context.moveTo(a.x, a.y);
          context.lineTo(b.x, b.y);
        }
        context.stroke();
      }

      const labels: {
        text: string;
        x: number;
        y: number;
        strong: boolean;
        dim: boolean;
        weight: number;
      }[] = [];
      const showAll = scale > LABEL_SCALE;

      context.globalAlpha = 1;
      for (let index = 0; index < nodes.length; index += 1) {
        const body = list[index];
        if (!body) continue;
        const [name, group, nonTaggable] = nodes[index];
        const radius = radiusOf(degrees[index] ?? 0);
        const isFocus = index === focus;
        const isNear = near?.has(index) ?? false;
        const isMarked = marked ? marked.has(name) : true;
        const dimmed = (focus >= 0 && !isFocus && !isNear) || !isMarked;

        context.globalAlpha = dimmed ? 0.18 : 1;
        context.fillStyle = colours[group] ?? muted;
        context.beginPath();
        context.arc(body.x, body.y, radius, 0, Math.PI * 2);
        context.fill();

        if (nonTaggable) {
          context.strokeStyle = background;
          context.lineWidth = 2 / scale;
          context.stroke();
        }
        if (index === selectedIndex) {
          context.globalAlpha = 1;
          context.strokeStyle = foreground;
          context.lineWidth = 2.5 / scale;
          context.beginPath();
          context.arc(body.x, body.y, radius + 3.5, 0, Math.PI * 2);
          context.stroke();
        }

        if (
          isFocus ||
          isNear ||
          index === selectedIndex ||
          showAll ||
          (hubs.has(index) && !dimmed) ||
          (marked && marked.size <= 14 && isMarked)
        ) {
          labels.push({
            text: name,
            x: body.x,
            y: body.y - radius - 4 / scale,
            strong: isFocus || index === selectedIndex,
            dim: dimmed,
            weight: degrees[index] ?? 0,
          });
        }
      }

      // Labels last and grouped by weight: `context.font` is a parsed string, and
      // setting it per node was most of the per-frame cost at this node count. The
      // ones the user asked for (focus, selection) are drawn first and always; the
      // rest give way to whatever is already on the canvas instead of overprinting it.
      context.textAlign = "center";
      context.textBaseline = "alphabetic";
      const placed: [number, number, number, number][] = [];
      const lineHeight = 13 / scale;

      const paint = (strong: boolean) => {
        const chosen = labels
          .filter((label) => label.strong === strong)
          .sort((a, b) => b.weight - a.weight);
        if (chosen.length === 0) return;
        context.font = `${strong ? 600 : 400} ${11 / scale}px ui-sans-serif, system-ui`;
        context.fillStyle = strong ? foreground : muted;
        for (const label of chosen) {
          const half = context.measureText(label.text).width / 2;
          const box: [number, number, number, number] = [
            label.x - half,
            label.y - lineHeight,
            label.x + half,
            label.y + lineHeight * 0.3,
          ];
          if (!strong && placed.some((r) => box[0] < r[2] && box[2] > r[0] && box[1] < r[3] && box[3] > r[1])) {
            continue;
          }
          placed.push(box);
          context.globalAlpha = label.dim ? 0.3 : 1;
          context.fillText(label.text, label.x, label.y);
        }
      };
      paint(true);
      paint(false);

      context.globalAlpha = 1;
      context.restore();
    };

    loopRef.current = () => {
      frame.current = null;
      const hot = temperature.current > SETTLED;
      if (hot) {
        simulate();
        dirty.current = true;
      }
      // The camera follows the relaxation while it expands and stops when it settles,
      // so the graph is never half off-canvas — and one pan or zoom hands it over.
      if (pendingFit.current) {
        applyFit();
        dirty.current = true;
        if (!hot) pendingFit.current = false;
      }
      if (dirty.current) {
        draw();
        dirty.current = false;
      }
      if (hot) frame.current = requestAnimationFrame(() => loopRef.current());
    };

    // The frame is the world, so a resized panel needs the layout to flow into it —
    // a gentle reheat, not the full relaxation the user already watched once.
    let known = { width: 0, height: 0 };
    const observer = new ResizeObserver(() => {
      syncSize();
      const changed =
        Math.abs(known.width - size.current.width) > 24 ||
        Math.abs(known.height - size.current.height) > 24;
      if (changed && known.width > 0) reheat(0.25);
      known = { ...size.current };
      wake();
    });
    observer.observe(wrap);
    syncSize();
    known = { ...size.current };

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onTheme = () => {
      palette.current = readPalette();
      repaint();
    };
    media.addEventListener("change", onTheme);

    // Non-passive, because the page must not scroll while the wheel is zooming.
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      takeCamera();
      const rect = canvas.getBoundingClientRect();
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.current.scale * factor));
      const ratio = next / view.current.scale;
      // Keep the point under the cursor still: zoom around it, not around the centre.
      const offsetX = event.clientX - rect.left - rect.width / 2;
      const offsetY = event.clientY - rect.top - rect.height / 2;
      view.current.x = offsetX - (offsetX - view.current.x) * ratio;
      view.current.y = offsetY - (offsetY - view.current.y) * ratio;
      view.current.scale = next;
      repaint();
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });

    wake();

    return () => {
      observer.disconnect();
      media.removeEventListener("change", onTheme);
      canvas.removeEventListener("wheel", onWheel);
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
    };
  }, [applyFit, reheat, repaint, takeCamera, wake]);

  const zoom = (factor: number) => {
    takeCamera();
    view.current.scale = Math.min(
      MAX_SCALE,
      Math.max(MIN_SCALE, view.current.scale * factor),
    );
    repaint();
  };

  const toWorld = (event: { clientX: number; clientY: number }) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left - rect.width / 2 - view.current.x) / view.current.scale,
      y: (event.clientY - rect.top - rect.height / 2 - view.current.y) / view.current.scale,
    };
  };

  const pick = (event: { clientX: number; clientY: number }) => {
    const world = toWorld(event);
    const { degrees } = modelRef.current;
    let best = -1;
    let bestDistance = Infinity;
    bodies.current.forEach((body, index) => {
      const distance = Math.hypot(body.x - world.x, body.y - world.y);
      const radius = radiusOf(degrees[index] ?? 0) + 4 / view.current.scale;
      if (distance < radius && distance < bestDistance) {
        best = index;
        bestDistance = distance;
      }
    });
    return best;
  };

  const release = () => {
    const state = pointer.current;
    if (state.mode === "node" && bodies.current[state.index]) {
      bodies.current[state.index].pinned = false;
    }
    pointer.current = { mode: "none", index: -1, x: 0, y: 0, moved: 0 };
  };

  return (
    <div
      ref={wrapRef}
      className={cn(
        "relative h-full w-full overflow-hidden rounded-lg border border-border bg-card",
        className,
      )}
    >
      <canvas
        ref={canvasRef}
        className="block h-full w-full touch-none cursor-grab active:cursor-grabbing"
        onPointerDown={(event) => {
          (event.target as HTMLCanvasElement).setPointerCapture(event.pointerId);
          const index = pick(event);
          pointer.current = {
            mode: index >= 0 ? "node" : "pan",
            index,
            x: event.clientX,
            y: event.clientY,
            moved: 0,
          };
          if (index >= 0) bodies.current[index].pinned = true;
        }}
        onPointerMove={(event) => {
          const state = pointer.current;
          if (state.mode === "none") {
            const index = pick(event);
            const next = index >= 0 ? index : null;
            if (next !== hoveredRef.current) setHovered(next);
            return;
          }
          const deltaX = event.clientX - state.x;
          const deltaY = event.clientY - state.y;
          state.x = event.clientX;
          state.y = event.clientY;
          state.moved += Math.abs(deltaX) + Math.abs(deltaY);
          if (state.moved > 3) takeCamera();
          if (state.mode === "pan") {
            view.current.x += deltaX;
            view.current.y += deltaY;
          } else {
            const body = bodies.current[state.index];
            body.x += deltaX / view.current.scale;
            body.y += deltaY / view.current.scale;
          }
          repaint();
        }}
        onPointerUp={(event) => {
          const state = pointer.current;
          if (state.mode === "node") {
            if (state.moved < 4) onSelect(graph.nodes[state.index][0]);
          } else if (state.mode === "pan" && state.moved < 4 && pick(event) < 0) {
            onSelect(null);
          }
          release();
        }}
        onPointerCancel={release}
        onPointerLeave={() => {
          setHovered(null);
          if (pointer.current.mode !== "none") release();
        }}
      />

      <div className="absolute right-2 top-2 flex flex-col gap-1">
        <Button variant="secondary" size="icon-sm" onClick={() => zoom(1.2)} aria-label="Acercar">
          <ZoomIn />
        </Button>
        <Button variant="secondary" size="icon-sm" onClick={() => zoom(1 / 1.2)} aria-label="Alejar">
          <ZoomOut />
        </Button>
        <Button variant="secondary" size="icon-sm" onClick={fit} aria-label="Encuadrar" title="Encuadrar todo">
          <Maximize2 />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={() => {
            pendingFit.current = true;
            reheat();
          }}
          aria-label="Recolocar"
          title="Recolocar el grafo"
        >
          <RotateCw />
        </Button>
      </div>

      {hovered !== null && graph.nodes[hovered] ? (
        <div className="pointer-events-none absolute bottom-2 left-2 rounded-md border border-border bg-popover/95 px-2 py-1 text-xs shadow">
          <span className="font-medium">{graph.nodes[hovered][0]}</span>
          <span className="ml-2 text-muted-foreground">
            {graph.groups[graph.nodes[hovered][1]]?.name} · grado {model.degrees[hovered] ?? 0}
          </span>
        </div>
      ) : null}
    </div>
  );
}
