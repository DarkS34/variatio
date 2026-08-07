import { Maximize2, Network, RotateCw, Tag, Waypoints, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { GraphView } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  draw,
  drawMinimap,
  radiusOf,
  readPalette,
  type LabelMode,
  type Scene,
} from "./graph/draw";
import {
  curriculumPositions,
  forceStep,
  PADDING,
  seedBodies,
  settleTowardTargets,
  type Body,
  type LayoutMode,
} from "./graph/layout";
import { buildModel } from "./graph/model";

/**
 * The knowledge graph, drawn by hand on a canvas, in two layouts.
 *
 * A curriculum graph is two things at once and no single picture shows both: a web of
 * semantic neighbourhoods, which a force layout shows and a layered one destroys, and
 * an ORDER of prerequisites, which a force layout hides completely. So the engine owns
 * both and animates between them — `layout.ts` produces positions, `draw.ts` paints,
 * and this file owns the loop, the camera and the pointer.
 *
 * Owning the loop means owning when it stops. Three rules keep it cheap: a frame is
 * only requested while the layout is moving or something changed; nothing inside a
 * frame reads the DOM (size comes from a ResizeObserver, colours from a cached
 * palette — both used to force a reflow on every single frame); and the props the
 * drawing depends on live in refs, so a keystroke in the search box repaints instead
 * of tearing down and restarting the animation.
 */

interface Props {
  graph: GraphView;
  selected: string | null;
  onSelect: (concept: string | null) => void;
  highlight?: Set<string>;
  hiddenRelations?: Set<number>;
  className?: string;
}

const MIN_SCALE = 0.15;
const MAX_SCALE = 4;
const SETTLED = 0.4;
const COOLING = 0.975;
const MINIMAP = { width: 150, height: 104, margin: 10 };

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
  const settling = useRef(false);
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
  const [tip, setTip] = useState({ x: 0, y: 0 });
  const hoveredRef = useRef<number | null>(null);
  hoveredRef.current = hovered;

  const [mode, setMode] = useState<LayoutMode>("force");
  const [labels, setLabels] = useState<LabelMode>("auto");
  const [arrows, setArrows] = useState(true);

  const model = useMemo(() => buildModel(graph), [graph]);

  const modelRef = useRef(model);
  modelRef.current = model;
  const graphRef = useRef(graph);
  graphRef.current = graph;
  const viewProps = useRef({ selected, highlight, hiddenRelations, mode, labels, arrows });
  viewProps.current = { selected, highlight, hiddenRelations, mode, labels, arrows };

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
    view.current = { x: -((minX + maxX) / 2) * scale, y: -((minY + maxY) / 2) * scale, scale };
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

  const relayout = useCallback(() => {
    pendingFit.current = true;
    if (viewProps.current.mode === "curriculum") {
      const targets = curriculumPositions(graphRef.current, modelRef.current);
      bodies.current.forEach((body, index) => {
        body.pinned = false;
        body.tx = targets[index]?.x ?? body.x;
        body.ty = targets[index]?.y ?? body.y;
      });
      settling.current = true;
      wake();
      return;
    }
    bodies.current = seedBodies(graphRef.current, size.current);
    reheat();
  }, [reheat, wake]);

  useEffect(() => {
    bodies.current = seedBodies(graph, size.current);
    pendingFit.current = true;
    settling.current = false;
    reheat();
    repaint();
  }, [graph, reheat, repaint]);

  // Switching layout never rebuilds the bodies: each one is given a target and eased
  // into it, so the same node stays the same dot and you can watch the cloud fold into
  // levels. That continuity is the whole reason both views live in one canvas.
  useEffect(() => {
    if (mode === "curriculum") {
      const targets = curriculumPositions(graph, model);
      bodies.current.forEach((body, index) => {
        body.pinned = false;
        body.tx = targets[index]?.x ?? body.x;
        body.ty = targets[index]?.y ?? body.y;
      });
      temperature.current = 0;
      settling.current = true;
    } else {
      settling.current = false;
      reheat(0.55);
    }
    pendingFit.current = true;
    wake();
  }, [mode, graph, model, reheat, wake]);

  // Selection, search highlight and filters change what is drawn, never the simulation:
  // mark the canvas dirty and let the loop draw one more frame.
  useEffect(() => {
    repaint();
  }, [selected, highlight, hiddenRelations, hovered, labels, arrows, repaint]);

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

    const scene = (): Scene => {
      const props = viewProps.current;
      const current = props.selected ? (modelRef.current.nameIndex.get(props.selected) ?? -1) : -1;
      return {
        graph: graphRef.current,
        model: modelRef.current,
        bodies: bodies.current,
        view: view.current,
        frame: size.current,
        palette: palette.current,
        mode: props.mode,
        labels: props.labels,
        arrows: props.arrows,
        hulls: true,
        selected: current,
        focused: hoveredRef.current ?? -1,
        highlight: props.highlight,
        hiddenRelations: props.hiddenRelations,
      };
    };

    loopRef.current = () => {
      frame.current = null;
      const curriculum = viewProps.current.mode === "curriculum";
      let moving = false;

      if (curriculum && settling.current) {
        moving = settleTowardTargets(bodies.current);
        settling.current = moving;
      } else if (!curriculum && temperature.current > SETTLED) {
        forceStep(
          bodies.current,
          graphRef.current.links,
          size.current,
          temperature.current,
          viewProps.current.hiddenRelations,
        );
        temperature.current *= COOLING;
        moving = true;
      }
      if (moving) dirty.current = true;

      // The camera follows the layout while it moves and stops when it settles, so the
      // graph is never half off-canvas — and one pan or zoom hands it over for good.
      if (pendingFit.current) {
        applyFit();
        dirty.current = true;
        if (!moving) pendingFit.current = false;
      }

      if (dirty.current) {
        const current = scene();
        draw(context, current);
        drawMinimap(context, current, {
          x: size.current.width - MINIMAP.width - MINIMAP.margin,
          y: size.current.height - MINIMAP.height - MINIMAP.margin,
          width: MINIMAP.width,
          height: MINIMAP.height,
        });
        dirty.current = false;
      }
      if (moving) frame.current = requestAnimationFrame(() => loopRef.current());
    };

    // The frame is the world in force mode, so a resized panel needs the layout to flow
    // into it — a gentle reheat, not the full relaxation the user already watched once.
    let known = { width: 0, height: 0 };
    const observer = new ResizeObserver(() => {
      syncSize();
      const changed =
        Math.abs(known.width - size.current.width) > 24 ||
        Math.abs(known.height - size.current.height) > 24;
      if (changed && known.width > 0 && viewProps.current.mode === "force") reheat(0.25);
      known = { ...size.current };
      wake();
    });
    observer.observe(wrap);
    syncSize();
    known = { ...size.current };
    if (bodies.current.length === 0) bodies.current = seedBodies(graphRef.current, size.current);

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
    view.current.scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.current.scale * factor));
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
      const radius = radiusOf(degrees[index] ?? 0) + 5 / view.current.scale;
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

  const hoveredNode = hovered !== null ? graph.nodes[hovered] : undefined;

  return (
    <div
      ref={wrapRef}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "f") fit();
        if (event.key === "Escape") onSelect(null);
      }}
      className={cn(
        "relative h-full w-full overflow-hidden rounded-lg border border-border bg-card outline-none focus-visible:ring-2 focus-visible:ring-ring",
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
            if (next !== null) {
              const rect = (event.target as HTMLCanvasElement).getBoundingClientRect();
              setTip({ x: event.clientX - rect.left, y: event.clientY - rect.top });
            }
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
            // In the layered view a body is held by its target, not by the simulation:
            // move the target too or it springs back the moment you let go.
            body.tx = body.x;
            body.ty = body.y;
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

      <div className="pointer-events-auto absolute left-2 top-2 flex items-center gap-1 rounded-md border border-border bg-card/90 p-0.5 shadow-sm backdrop-blur">
        {(
          [
            { value: "force", label: "Vecindario", icon: Network, hint: "Conceptos cerca de aquellos con los que se relacionan" },
            {
              value: "curriculum",
              label: "Currículo",
              icon: Waypoints,
              hint: model.curriculumEdges
                ? `Un nivel por profundidad de prerrequisitos: lo de arriba se enseña antes (${model.curriculumEdges} relación(es) lo ordenan)`
                : "El grafo no tiene relaciones de prerrequisito que ordenar",
            },
          ] as const
        ).map((option) => (
          <button
            key={option.value}
            type="button"
            title={option.hint}
            disabled={option.value === "curriculum" && model.curriculumEdges === 0}
            onClick={() => setMode(option.value)}
            className={cn(
              "flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium transition-colors disabled:opacity-40",
              mode === option.value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <option.icon className="size-3.5" />
            {option.label}
          </button>
        ))}
      </div>

      <div className="absolute right-2 top-2 flex flex-col gap-1">
        <Button variant="secondary" size="icon-sm" onClick={() => zoom(1.2)} aria-label="Acercar">
          <ZoomIn />
        </Button>
        <Button variant="secondary" size="icon-sm" onClick={() => zoom(1 / 1.2)} aria-label="Alejar">
          <ZoomOut />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={fit}
          aria-label="Encuadrar"
          title="Encuadrar todo (F)"
        >
          <Maximize2 />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={relayout}
          aria-label="Recolocar"
          title="Recolocar el grafo"
        >
          <RotateCw />
        </Button>
        <Button
          variant={labels === "none" ? "outline" : "secondary"}
          size="icon-sm"
          onClick={() => setLabels(labels === "auto" ? "all" : labels === "all" ? "none" : "auto")}
          aria-label="Etiquetas"
          title={
            labels === "auto"
              ? "Etiquetas: automáticas (clic para verlas todas)"
              : labels === "all"
                ? "Etiquetas: todas (clic para ocultarlas)"
                : "Etiquetas: ocultas (clic para volver a automáticas)"
          }
        >
          <Tag />
        </Button>
      </div>

      <div className="pointer-events-none absolute bottom-2 left-2 flex flex-col gap-1">
        <button
          type="button"
          onClick={() => setArrows(!arrows)}
          className="pointer-events-auto w-fit rounded-md border border-border bg-card/90 px-2 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur transition-colors hover:text-foreground"
        >
          {arrows ? "Ocultar sentido" : "Mostrar sentido"}
        </button>
        <span className="w-fit rounded-md border border-border bg-card/90 px-2 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur">
          {graph.nodes.length} conceptos · {graph.links.length} relaciones
          {graph.meta.isolated > 0 ? ` · ${graph.meta.isolated} aislados` : ""}
        </span>
      </div>

      {/* Un grafo con pocos prerrequisitos apila casi todo en el nivel 0. Eso es un dato
          sobre el grafo, no un fallo de la vista: decirlo evita que parezca lo segundo. */}
      {mode === "curriculum" && model.levelCount < 3 ? (
        <p className="pointer-events-none absolute left-1/2 top-12 max-w-md -translate-x-1/2 rounded-md border border-[color-mix(in_oklch,var(--warning)_40%,transparent)] bg-[color-mix(in_oklch,var(--warning)_12%,var(--card))] px-3 py-1.5 text-center text-[11px] shadow-sm">
          Solo {model.curriculumEdges} relación(es) de prerrequisito ordenan {graph.nodes.length}{" "}
          conceptos, así que casi todo cae en el nivel 0. Añade prerrequisitos en el detalle de cada
          concepto para que esta vista diga algo.
        </p>
      ) : null}

      {hoveredNode ? (
        <div
          className="pointer-events-none absolute z-10 max-w-64 rounded-md border border-border bg-popover/95 px-2 py-1 text-xs shadow-lg backdrop-blur"
          style={{
            left: Math.min(tip.x + 14, Math.max(0, size.current.width - 260)),
            top: Math.max(4, tip.y - 46),
          }}
        >
          <p className="font-medium">{hoveredNode[0]}</p>
          <p className="text-muted-foreground">
            {graph.groups[hoveredNode[1]]?.name} · grado {model.degrees[hovered!] ?? 0}
            {mode === "curriculum" && model.curriculumEdges > 0
              ? ` · nivel ${model.levels[hovered!]}`
              : ""}
          </p>
          {hoveredNode[2] ? <p className="text-muted-foreground">no etiquetable</p> : null}
        </div>
      ) : null}
    </div>
  );
}
