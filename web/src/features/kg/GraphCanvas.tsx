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

export function GraphCanvas({
  graph,
  selected,
  onSelect,
  highlight,
  hiddenRelations,
  className,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const bodies = useRef<Body[]>([]);
  const view = useRef({ x: 0, y: 0, scale: 1 });
  const temperature = useRef(0);
  const pointer = useRef<{ mode: "none" | "pan" | "node"; index: number; x: number; y: number }>({
    mode: "none",
    index: -1,
    x: 0,
    y: 0,
  });
  const [hovered, setHovered] = useState<number | null>(null);
  const hoveredRef = useRef<number | null>(null);
  hoveredRef.current = hovered;

  const nodeCount = graph.nodes.length;

  const adjacency = useMemo(() => {
    const map = new Map<number, Set<number>>();
    for (const [source, target] of graph.links) {
      if (!map.has(source)) map.set(source, new Set());
      if (!map.has(target)) map.set(target, new Set());
      map.get(source)!.add(target);
      map.get(target)!.add(source);
    }
    return map;
  }, [graph.links]);

  const degrees = useMemo(() => {
    const counts = new Array(nodeCount).fill(0);
    for (const [source, target] of graph.links) {
      counts[source] += 1;
      counts[target] += 1;
    }
    return counts;
  }, [graph.links, nodeCount]);

  const nameIndex = useMemo(() => {
    const map = new Map<string, number>();
    graph.nodes.forEach(([name], index) => map.set(name, index));
    return map;
  }, [graph.nodes]);

  const reheat = useCallback(() => {
    temperature.current = 60;
  }, []);

  // Seed on a circle: a deterministic start makes the layout reproducible between
  // reloads, which matters when you are comparing the graph to a list beside it.
  useEffect(() => {
    bodies.current = graph.nodes.map((_, index) => {
      const angle = (index / Math.max(1, nodeCount)) * Math.PI * 2;
      const radius = 220 + (index % 7) * 18;
      return {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        dx: 0,
        dy: 0,
        pinned: false,
      };
    });
    view.current = { x: 0, y: 0, scale: 1 };
    reheat();
  }, [graph, nodeCount, reheat]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    let frame = 0;

    const step = () => {
      const parent = canvas.parentElement;
      const width = parent?.clientWidth ?? 800;
      const height = parent?.clientHeight ?? 600;
      const ratio = window.devicePixelRatio || 1;

      if (canvas.width !== width * ratio || canvas.height !== height * ratio) {
        canvas.width = width * ratio;
        canvas.height = height * ratio;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
      }

      if (temperature.current > 0.35) simulate(width, height);
      draw(context, width, height, ratio);
      frame = requestAnimationFrame(step);
    };

    const simulate = (width: number, height: number) => {
      const list = bodies.current;
      const n = list.length;
      if (n === 0) return;
      const k = Math.sqrt((width * height) / n) * 0.8;

      for (const body of list) {
        body.dx = 0;
        body.dy = 0;
      }

      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          let deltaX = list[i].x - list[j].x;
          let deltaY = list[i].y - list[j].y;
          let distance = Math.hypot(deltaX, deltaY);
          if (distance < 0.01) {
            deltaX = Math.random() - 0.5;
            deltaY = Math.random() - 0.5;
            distance = 0.01;
          }
          const force = (k * k) / distance;
          const ux = (deltaX / distance) * force;
          const uy = (deltaY / distance) * force;
          list[i].dx += ux;
          list[i].dy += uy;
          list[j].dx -= ux;
          list[j].dy -= uy;
        }
      }

      for (const [source, target, relation] of graph.links) {
        if (hiddenRelations?.has(relation)) continue;
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

      const temp = temperature.current;
      for (const body of list) {
        if (body.pinned) continue;
        // Gravity keeps disconnected concepts from drifting off the canvas forever;
        // weak enough that it does not crush the clusters into the middle.
        body.dx -= body.x * 0.035;
        body.dy -= body.y * 0.035;
        const magnitude = Math.max(0.01, Math.hypot(body.dx, body.dy));
        const move = Math.min(magnitude, temp);
        body.x += (body.dx / magnitude) * move;
        body.y += (body.dy / magnitude) * move;
      }
      temperature.current = temp * 0.978;
    };

    const draw = (context: CanvasRenderingContext2D, width: number, height: number, ratio: number) => {
      const styles = getComputedStyle(document.documentElement);
      const foreground = styles.getPropertyValue("--foreground").trim() || "#111";
      const muted = styles.getPropertyValue("--muted-foreground").trim() || "#888";
      const border = styles.getPropertyValue("--border").trim() || "#ddd";

      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      context.save();
      context.translate(width / 2 + view.current.x, height / 2 + view.current.y);
      context.scale(view.current.scale, view.current.scale);

      const list = bodies.current;
      const selectedIndex = selected ? (nameIndex.get(selected) ?? -1) : -1;
      const focus = hoveredRef.current !== null ? hoveredRef.current : selectedIndex;
      const near = focus >= 0 ? adjacency.get(focus) : undefined;

      context.lineWidth = 1 / view.current.scale;
      for (const [source, target, relation] of graph.links) {
        if (hiddenRelations?.has(relation)) continue;
        const a = list[source];
        const b = list[target];
        if (!a || !b) continue;
        const related = focus >= 0 && (source === focus || target === focus);
        context.strokeStyle = related ? foreground : border;
        context.globalAlpha = focus >= 0 ? (related ? 0.8 : 0.15) : 0.55;
        context.beginPath();
        context.moveTo(a.x, a.y);
        context.lineTo(b.x, b.y);
        context.stroke();
      }
      context.globalAlpha = 1;

      const groupCount = graph.groups.length;
      graph.nodes.forEach(([name, group, nonTaggable], index) => {
        const body = list[index];
        if (!body) return;
        const radius = 4 + Math.min(9, Math.sqrt(degrees[index] ?? 0) * 2.2);
        const isFocus = index === focus;
        const isNear = near?.has(index) ?? false;
        const isHighlighted = highlight ? highlight.has(name) : true;
        const dimmed = (focus >= 0 && !isFocus && !isNear) || !isHighlighted;

        context.globalAlpha = dimmed ? 0.22 : 1;
        context.fillStyle = domainColour(group, groupCount);
        context.beginPath();
        context.arc(body.x, body.y, radius, 0, Math.PI * 2);
        context.fill();

        if (nonTaggable) {
          context.strokeStyle = styles.getPropertyValue("--background").trim() || "#fff";
          context.lineWidth = 2 / view.current.scale;
          context.stroke();
        }
        if (index === selectedIndex) {
          context.strokeStyle = foreground;
          context.lineWidth = 2.5 / view.current.scale;
          context.beginPath();
          context.arc(body.x, body.y, radius + 3.5, 0, Math.PI * 2);
          context.stroke();
        }

        const showLabel =
          isFocus || isNear || index === selectedIndex || view.current.scale > 1.25 || (highlight && highlight.size <= 12 && isHighlighted);
        if (showLabel) {
          context.globalAlpha = dimmed ? 0.3 : 1;
          context.fillStyle = isFocus || index === selectedIndex ? foreground : muted;
          context.font = `${isFocus ? 600 : 400} ${11 / view.current.scale}px ui-sans-serif, system-ui`;
          context.textAlign = "center";
          context.fillText(name, body.x, body.y - radius - 4 / view.current.scale);
        }
      });

      context.globalAlpha = 1;
      context.restore();
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [graph, adjacency, degrees, nameIndex, selected, highlight, hiddenRelations]);

  const toWorld = (event: { clientX: number; clientY: number }) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left - rect.width / 2 - view.current.x) / view.current.scale,
      y: (event.clientY - rect.top - rect.height / 2 - view.current.y) / view.current.scale,
    };
  };

  const pick = (event: { clientX: number; clientY: number }) => {
    const world = toWorld(event);
    let best = -1;
    let bestDistance = Infinity;
    bodies.current.forEach((body, index) => {
      const distance = Math.hypot(body.x - world.x, body.y - world.y);
      const radius = 6 + Math.min(9, Math.sqrt(degrees[index] ?? 0) * 2.2);
      if (distance < radius + 4 && distance < bestDistance) {
        best = index;
        bestDistance = distance;
      }
    });
    return best;
  };

  return (
    <div className={cn("relative h-full w-full overflow-hidden rounded-lg border border-border bg-card", className)}>
      <canvas
        ref={canvasRef}
        className="block h-full w-full cursor-grab active:cursor-grabbing"
        onPointerDown={(event) => {
          (event.target as HTMLCanvasElement).setPointerCapture(event.pointerId);
          const index = pick(event);
          pointer.current = {
            mode: index >= 0 ? "node" : "pan",
            index,
            x: event.clientX,
            y: event.clientY,
          };
          if (index >= 0) bodies.current[index].pinned = true;
        }}
        onPointerMove={(event) => {
          const state = pointer.current;
          if (state.mode === "none") {
            const index = pick(event);
            if (index !== hoveredRef.current) setHovered(index >= 0 ? index : null);
            return;
          }
          const deltaX = event.clientX - state.x;
          const deltaY = event.clientY - state.y;
          state.x = event.clientX;
          state.y = event.clientY;
          if (state.mode === "pan") {
            view.current.x += deltaX;
            view.current.y += deltaY;
          } else {
            const body = bodies.current[state.index];
            body.x += deltaX / view.current.scale;
            body.y += deltaY / view.current.scale;
            reheat();
          }
        }}
        onPointerUp={(event) => {
          const state = pointer.current;
          if (state.mode === "node") {
            bodies.current[state.index].pinned = false;
            const moved = Math.hypot(event.clientX - state.x, event.clientY - state.y);
            if (moved < 3) onSelect(graph.nodes[state.index][0]);
          } else if (state.mode === "pan") {
            const index = pick(event);
            if (index < 0) onSelect(null);
          }
          pointer.current = { mode: "none", index: -1, x: 0, y: 0 };
        }}
        onWheel={(event) => {
          const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
          const next = Math.min(4, Math.max(0.25, view.current.scale * factor));
          view.current.scale = next;
        }}
        onPointerLeave={() => setHovered(null)}
      />

      <div className="absolute right-2 top-2 flex flex-col gap-1">
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={() => (view.current.scale = Math.min(4, view.current.scale * 1.2))}
          aria-label="Acercar"
        >
          <ZoomIn />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={() => (view.current.scale = Math.max(0.25, view.current.scale / 1.2))}
          aria-label="Alejar"
        >
          <ZoomOut />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={() => {
            view.current = { x: 0, y: 0, scale: 1 };
          }}
          aria-label="Encuadrar"
        >
          <Maximize2 />
        </Button>
        <Button variant="secondary" size="icon-sm" onClick={reheat} aria-label="Recolocar">
          <RotateCw />
        </Button>
      </div>

      {hovered !== null ? (
        <div className="pointer-events-none absolute bottom-2 left-2 rounded-md border border-border bg-popover/95 px-2 py-1 text-xs shadow">
          <span className="font-medium">{graph.nodes[hovered][0]}</span>
          <span className="ml-2 text-muted-foreground">
            {graph.groups[graph.nodes[hovered][1]]?.name} · grado {degrees[hovered] ?? 0}
          </span>
        </div>
      ) : null}
    </div>
  );
}
