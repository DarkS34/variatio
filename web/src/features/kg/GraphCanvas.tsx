import { Maximize2, Network, RotateCw, Tag, Waypoints, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import type { GraphView } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  detailAt,
  draw,
  drawMinimap,
  drawnRadius,
  READING_SCALE,
  readPalette,
  type LabelMode,
  type Scene,
  type View,
} from "./graph/draw";
import { LabelGrid } from "./graph/labels";
import {
  curriculumPositions,
  PADDING,
  settleTowardTargets,
  type Body,
  type LayoutMode,
} from "./graph/layout";
import { cachedLayout, requestLayout } from "./graph/layoutClient";
import { layoutKey, regionsOf, type Lane, type MapLayout } from "./graph/mapLayout";
import { buildModel, frontierOf } from "./graph/model";
import type { Region } from "./graph/regions";

/**
 * The knowledge graph, drawn by hand on a canvas, in two layouts.
 *
 * A curriculum graph is two things at once and no single picture shows both: a web of
 * semantic neighbourhoods and an ORDER of prerequisites. So the canvas owns both and eases
 * between them. What changed with the subjects of thousands of concepts is where the first one
 * comes from. It used to be simulated here, on the main thread, from scratch on every visit —
 * measured on the nursing subject (2 496 concepts), 47 s of a frozen page before the first
 * frame, and again for the expanded view. Now the map is laid out ONCE per structure, in a
 * worker, with every unit a region of its own (`graph/mapLayout.ts`), and kept in memory and in
 * `localStorage` (`graph/layoutClient.ts`); this file only draws it, moves the camera and eases
 * the bodies when a new map lands.
 *
 * Three rules keep the loop cheap: a frame is only requested while something moves or
 * changed; nothing inside a frame reads the DOM; and the props the drawing depends on live in
 * refs, so a keystroke in the search box repaints instead of restarting anything.
 */

interface Props {
  graph: GraphView;
  selected: string | null;
  onSelect: (concept: string | null) => void;
  picked?: Set<string>;
  onPick?: (concept: string) => void;
  initialMode?: LayoutMode;
  highlight?: Set<string>;
  hiddenRelations?: Set<number>;
  /** Concepts the course has covered. `undefined` — NOT an empty set — means no curriculum
   *  is in force and the graph keeps its domain colours; an empty set is a course that has
   *  covered nothing yet, which is a different statement and is drawn as one. */
  curriculum?: Set<string>;
  /** Drop the toolbars and keep the drawing. Panning, zooming, hovering and selecting all
   *  still work here; only the chrome goes, to the expanded view one click away. */
  compact?: boolean;
  className?: string;
}

const MAX_SCALE = 4;
const MINIMAP = { width: 150, height: 104, margin: 10 };
// A map that lands sooner than this is drawn with no caption at all: announcing a wait that
// is over before it can be read is noise.
const PLACING_DELAY = 250;
const FLY_MS = 420;
// Below this much detail a click is about a UNIT: concepts are specks there, and a speck
// under the pointer is an accident, not a choice.
const UNIT_CLICKS_BELOW = 0.35;

interface Placement {
  regions: Region[];
  lanes: Lane[];
  width: number;
  height: number;
}

export function GraphCanvas({
  graph,
  selected,
  onSelect,
  picked,
  onPick,
  initialMode,
  highlight,
  hiddenRelations,
  curriculum,
  compact = false,
  className,
}: Props) {
  const { t, plural } = useT();
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const bodies = useRef<Body[]>([]);
  const view = useRef<View>({ x: 0, y: 0, scale: 1 });
  const minScale = useRef(0.15);
  const settling = useRef(false);
  const size = useRef({ width: 0, height: 0 });
  const palette = useRef(readPalette());
  const dirty = useRef(true);
  const frame = useRef<number | null>(null);
  // The camera frames the whole map until somebody pans or zooms it themselves.
  const pendingFit = useRef(true);
  const framed = useRef(true);
  const loopRef = useRef<() => void>(() => {});
  const flight = useRef<{ from: View; to: View; start: number } | null>(null);
  const grid = useRef(new LabelGrid());
  const placement = useRef<Placement>({ regions: [], lanes: [], width: 0, height: 0 });
  const layoutRef = useRef<MapLayout | null>(null);
  // The map on screen and the graph it belongs to: where the next one starts from.
  const shown = useRef<{ graph: GraphView; layout: MapLayout } | null>(null);
  const flyWanted = useRef<string | null>(null);
  const pickedHere = useRef<string | null>(null);

  const pointer = useRef<{
    mode: "none" | "pan" | "node";
    index: number;
    x: number;
    y: number;
    moved: number;
  }>({ mode: "none", index: -1, x: 0, y: 0, moved: 0 });

  const [hovered, setHovered] = useState<number | null>(null);
  const [hoveredUnit, setHoveredUnit] = useState<number | null>(null);
  const [tip, setTip] = useState({ x: 0, y: 0 });
  const [placing, setPlacing] = useState(false);
  const hoveredRef = useRef<number | null>(null);
  hoveredRef.current = hovered;

  const [mode, setMode] = useState<LayoutMode>(initialMode ?? "force");
  const [labels, setLabels] = useState<LabelMode>("auto");
  const [arrows, setArrows] = useState(true);

  const model = useMemo(() => buildModel(graph), [graph]);
  const widths = useMemo(() => new Float32Array(graph.nodes.length).fill(Number.NaN), [graph]);
  const onScreen = useMemo(() => new Uint8Array(graph.nodes.length), [graph]);
  const unitCounts = useMemo(
    () => graph.groups.map((group) => plural("canvas.conceptCount", group.count)),
    [graph, plural],
  );

  const pickedIndices = useMemo(() => {
    if (!picked) return undefined;
    const indices = new Set<number>();
    for (const name of picked) {
      const index = model.nameIndex.get(name);
      if (index !== undefined) indices.add(index);
    }
    return indices;
  }, [picked, model]);

  const modelRef = useRef(model);
  modelRef.current = model;
  const graphRef = useRef(graph);
  graphRef.current = graph;

  const curriculumIndices = useMemo(() => {
    if (!curriculum) return undefined;
    const indices = new Set<number>();
    for (const name of curriculum) {
      const index = model.nameIndex.get(name);
      if (index !== undefined) indices.add(index);
    }
    return indices;
  }, [curriculum, model]);

  const frontier = useMemo(
    () => (curriculumIndices ? frontierOf(graph, model, curriculumIndices) : undefined),
    [graph, model, curriculumIndices],
  );

  const viewProps = useRef({
    selected,
    picked: pickedIndices,
    highlight,
    hiddenRelations,
    mode,
    labels,
    arrows,
    compact,
    curriculum: curriculumIndices,
    frontier,
    unitCounts,
    widths,
    onScreen,
    laneCaption: (count: number) => plural("canvas.isolated", count),
  });
  viewProps.current = {
    selected,
    picked: pickedIndices,
    highlight,
    hiddenRelations,
    mode,
    labels,
    arrows,
    compact,
    curriculum: curriculumIndices,
    frontier,
    unitCounts,
    widths,
    onScreen,
    // The sentences the painter writes are passed in rather than translated there: it runs
    // every frame and knows nothing about the catalogue.
    laneCaption: (count: number) => plural("canvas.isolated", count),
  };

  const wake = useCallback(() => {
    if (frame.current === null) frame.current = requestAnimationFrame(() => loopRef.current());
  }, []);

  const repaint = useCallback(() => {
    dirty.current = true;
    wake();
  }, [wake]);

  /** What the camera frames: the whole map, or the order view's bands where they are heading. */
  const worldBounds = useCallback(() => {
    const plan = placement.current;
    if (viewProps.current.mode === "force" && plan.regions.length > 0) {
      // The regions themselves and not the map's rectangle: the half gutter around the outer
      // ones is empty, and in the card it would be an empty border.
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      for (const region of plan.regions) {
        minX = Math.min(minX, region.x);
        minY = Math.min(minY, region.y);
        maxX = Math.max(maxX, region.x + region.width);
        maxY = Math.max(maxY, region.y + region.height);
      }
      return { minX, minY, maxX, maxY };
    }
    const list = bodies.current;
    if (list.length === 0) return null;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const body of list) {
      if (body.tx < minX) minX = body.tx;
      if (body.ty < minY) minY = body.ty;
      if (body.tx > maxX) maxX = body.tx;
      if (body.ty > maxY) maxY = body.ty;
    }
    return { minX, minY, maxX, maxY };
  }, []);

  const frameOf = useCallback(
    (bounds: { minX: number; minY: number; maxX: number; maxY: number } | null): View | null => {
      const { width, height } = size.current;
      if (!bounds || width === 0 || height === 0) return null;
      const spanX = Math.max(1, bounds.maxX - bounds.minX);
      const spanY = Math.max(1, bounds.maxY - bounds.minY);
      // The card beside the outline has no toolbar to keep clear of, so the map is stretched
      // until one of its sides touches one of the card's — a pixel in, so the outer hairline
      // is not cut — while the expanded view leaves room for its chrome.
      const padding = viewProps.current.compact ? 1 : PADDING;
      const scale = Math.max(
        0.002,
        Math.min(MAX_SCALE, (width - padding * 2) / spanX, (height - padding * 2) / spanY),
      );
      return {
        x: -((bounds.minX + bounds.maxX) / 2) * scale,
        y: -((bounds.minY + bounds.maxY) / 2) * scale,
        scale,
      };
    },
    [],
  );

  const applyFit = useCallback(() => {
    const target = frameOf(worldBounds());
    if (!target) return false;
    // The expanded view does not blow a small subject up past 1.4×; the card fills itself.
    view.current = viewProps.current.compact
      ? target
      : { ...target, scale: Math.min(target.scale, 1.4) };
    // However big the subject, it can always be seen whole: the floor is below its own fit.
    minScale.current = Math.min(0.15, view.current.scale * 0.8);
    framed.current = true;
    return true;
  }, [frameOf, worldBounds]);

  const fit = useCallback(() => {
    flight.current = null;
    pendingFit.current = true;
    applyFit();
    repaint();
  }, [applyFit, repaint]);

  /** A manual pan, zoom or drag takes the camera from the automatic framing for good. */
  const takeCamera = useCallback(() => {
    pendingFit.current = false;
    framed.current = false;
    flight.current = null;
  }, []);

  const flyTo = useCallback(
    (to: View) => {
      pendingFit.current = false;
      framed.current = false;
      const reduced =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduced) {
        flight.current = null;
        view.current = to;
        repaint();
        return;
      }
      flight.current = { from: { ...view.current }, to, start: performance.now() };
      wake();
    },
    [repaint, wake],
  );

  /** Take the camera to a concept, close enough to read its neighbours' names. */
  const flyToConcept = useCallback(
    (name: string) => {
      const index = modelRef.current.nameIndex.get(name);
      const body = index === undefined ? undefined : bodies.current[index];
      if (!body || size.current.width === 0) {
        flyWanted.current = name;
        return;
      }
      flyWanted.current = null;
      const reading = viewProps.current.mode === "force" ? READING_SCALE : 1.1;
      const scale = Math.min(MAX_SCALE, Math.max(view.current.scale, reading));
      flyTo({ x: -body.tx * scale, y: -body.ty * scale, scale });
    },
    [flyTo],
  );

  /** Send every body toward `target(index)`: eased from where it is, or placed there at once. */
  const placeBodies = useCallback(
    (target: (index: number) => { x: number; y: number }, animate: boolean) => {
      const count = graphRef.current.nodes.length;
      const list = bodies.current;
      const fresh = list.length !== count;
      const next: Body[] = fresh ? new Array<Body>(count) : list;
      for (let index = 0; index < count; index += 1) {
        const { x, y } = target(index);
        const body = fresh ? undefined : list[index];
        if (!body) {
          next[index] = { x, y, tx: x, ty: y, pinned: false };
          continue;
        }
        body.tx = x;
        body.ty = y;
        body.pinned = false;
        if (!animate) {
          body.x = x;
          body.y = y;
        }
      }
      bodies.current = next;
      settling.current = animate && !fresh;
      repaint();
    },
    [repaint],
  );

  const land = useCallback(
    (layout: MapLayout, animate: boolean) => {
      layoutRef.current = layout;
      placement.current = {
        regions: layout.regions,
        lanes: layout.lanes,
        width: layout.width,
        height: layout.height,
      };
      shown.current = { graph: graphRef.current, layout };
      if (viewProps.current.mode === "force") {
        placeBodies(
          (index) => ({ x: layout.positions[index * 2], y: layout.positions[index * 2 + 1] }),
          animate,
        );
      }
      if (pendingFit.current || framed.current) applyFit();
      if (flyWanted.current) flyToConcept(flyWanted.current);
      repaint();
    },
    [applyFit, flyToConcept, placeBodies, repaint],
  );

  // A NEW GRAPH. The same structure — a description, a rename in place, a taggability switch —
  // keeps the map as it is. A new one is asked of the layout client; while it is computed the
  // units are drawn at once and, after an edit, the concepts already on screen stay where they
  // were, easing to their new places when the map lands.
  useEffect(() => {
    const key = layoutKey(graph);
    if (layoutRef.current?.key === key && bodies.current.length === graph.nodes.length) {
      shown.current = { graph, layout: layoutRef.current };
      repaint();
      return;
    }
    const previous = shown.current;
    const plan = regionsOf(graph);
    placement.current = { regions: plan.regions, lanes: [], width: plan.width, height: plan.height };
    layoutRef.current = null;

    if (viewProps.current.mode === "curriculum") {
      const targets = curriculumPositions(graph, model);
      placeBodies((index) => targets[index], false);
      if (!previous) pendingFit.current = true;
    } else if (previous) {
      const before = new Map(previous.graph.nodes.map(([name], index) => [name, index]));
      const centres = new Map(
        plan.regions.map((region) => [
          region.group,
          { x: region.x + region.width / 2, y: region.y + region.height / 2 },
        ]),
      );
      const old = bodies.current;
      bodies.current = graph.nodes.map(([name, group]) => {
        const index = before.get(name);
        const at = (index === undefined ? undefined : old[index]) ?? centres.get(group) ?? { x: 0, y: 0 };
        return { x: at.x, y: at.y, tx: at.x, ty: at.y, pinned: false };
      });
    } else {
      // Nothing to show yet but the units: no dot is drawn until it has its place.
      bodies.current = [];
      pendingFit.current = true;
    }

    const known = cachedLayout(key);
    if (known) {
      land(known, Boolean(previous));
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) setPlacing(true);
    }, PLACING_DELAY);
    requestLayout(graph, previous)
      .then((layout) => {
        if (!cancelled) land(layout, Boolean(previous));
      })
      .catch(() => undefined)
      .finally(() => {
        window.clearTimeout(timer);
        if (!cancelled) setPlacing(false);
      });
    if (pendingFit.current) applyFit();
    repaint();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [graph, model, applyFit, land, placeBodies, repaint]);

  // Switching layout never rebuilds the bodies: each one is given a target and eased into it,
  // so the same node stays the same dot and the map folds into its levels on screen.
  const firstMode = useRef(true);
  useEffect(() => {
    if (firstMode.current) {
      firstMode.current = false;
      return;
    }
    if (mode === "curriculum") {
      const targets = curriculumPositions(graphRef.current, modelRef.current);
      placeBodies((index) => targets[index], true);
    } else if (layoutRef.current) {
      const layout = layoutRef.current;
      placeBodies(
        (index) => ({ x: layout.positions[index * 2], y: layout.positions[index * 2 + 1] }),
        true,
      );
    }
    flight.current = null;
    pendingFit.current = true;
    wake();
  }, [mode, placeBodies, wake]);

  // A concept chosen somewhere else — the list, the flow — is flown to: with thousands of them
  // on the map, lighting one up where it already is would light up a speck. One chosen on the
  // canvas is already under the pointer and moves nothing.
  useEffect(() => {
    if (!selected) {
      flyWanted.current = null;
      if (compact && !framed.current) fit();
      return;
    }
    if (pickedHere.current === selected) {
      pickedHere.current = null;
      return;
    }
    flyToConcept(selected);
  }, [selected, compact, fit, flyToConcept]);

  // Selection, search highlight and filters change what is drawn, never the layout.
  useEffect(() => {
    repaint();
  }, [
    selected,
    pickedIndices,
    highlight,
    hiddenRelations,
    hovered,
    labels,
    arrows,
    curriculumIndices,
    frontier,
    repaint,
  ]);

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
        moving: settling.current || flight.current !== null,
        labels: props.labels,
        arrows: props.arrows,
        regions: placement.current.regions,
        lanes: placement.current.lanes,
        unitCounts: props.unitCounts,
        laneCaption: props.laneCaption,
        compact: props.compact,
        selected: current,
        picked: props.picked,
        focused: hoveredRef.current ?? -1,
        highlight: props.highlight,
        hiddenRelations: props.hiddenRelations,
        curriculum: props.curriculum,
        frontier: props.frontier,
        grid: grid.current,
        // Measured off the chrome as it is drawn below: the layout switch top-left, the
        // column of buttons top-right, the counters bottom-left and the minimap bottom-right.
        reserved: props.compact
          ? []
          : [
              [0, 0, 250, 44],
              [size.current.width - 46, 0, size.current.width, 186],
              [0, size.current.height - 74, 330, size.current.height],
              [
                size.current.width - MINIMAP.width - MINIMAP.margin - 4,
                size.current.height - MINIMAP.height - MINIMAP.margin - 4,
                size.current.width,
                size.current.height,
              ],
            ],
        widths: props.widths,
        onScreen: props.onScreen,
      };
    };

    loopRef.current = () => {
      frame.current = null;
      let moving = false;

      if (settling.current) {
        moving = settleTowardTargets(bodies.current);
        settling.current = moving;
      }

      const trip = flight.current;
      if (trip) {
        const t = Math.min(1, (performance.now() - trip.start) / FLY_MS);
        const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
        // The zoom travels geometrically and the centre linearly in world units, so the
        // journey reads as one even movement whatever the two zooms are.
        const scale = trip.from.scale * (trip.to.scale / trip.from.scale) ** eased;
        const fromX = -trip.from.x / trip.from.scale;
        const fromY = -trip.from.y / trip.from.scale;
        const toX = -trip.to.x / trip.to.scale;
        const toY = -trip.to.y / trip.to.scale;
        view.current = {
          x: -(fromX + (toX - fromX) * eased) * scale,
          y: -(fromY + (toY - fromY) * eased) * scale,
          scale,
        };
        if (t >= 1) flight.current = null;
        else moving = true;
      }
      if (moving) dirty.current = true;

      if (pendingFit.current) {
        const fitted = applyFit();
        if (fitted) dirty.current = true;
        if (fitted && !moving) pendingFit.current = false;
      }

      if (dirty.current) {
        const current = scene();
        draw(context, current);
        // The minimap is a map of the map, and at preview size it would cover a fifth of
        // the thing it summarises.
        if (!viewProps.current.compact) {
          drawMinimap(context, current, {
            x: size.current.width - MINIMAP.width - MINIMAP.margin,
            y: size.current.height - MINIMAP.height - MINIMAP.margin,
            width: MINIMAP.width,
            height: MINIMAP.height,
          });
        }
        dirty.current = false;
      }
      if (moving) frame.current = requestAnimationFrame(() => loopRef.current());
    };

    // A resized panel keeps what the reader framed; only the automatic framing follows it.
    const observer = new ResizeObserver(() => {
      syncSize();
      if (framed.current) applyFit();
      if (flyWanted.current) flyToConcept(flyWanted.current);
      wake();
    });
    observer.observe(wrap);
    syncSize();
    if (pendingFit.current) applyFit();

    // The stylesheet keys the dark tokens on `data-theme`, which `state/theme.ts` stamps
    // for the OS and for the toggle alike, so the attribute is the one thing to watch.
    const onTheme = new MutationObserver(() => {
      palette.current = readPalette();
      repaint();
    });
    onTheme.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    // Non-passive, because the page must not scroll while the wheel is zooming.
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      takeCamera();
      // What was under the pointer at the old zoom is not what is under it now.
      setHovered(null);
      setHoveredUnit(null);
      const rect = canvas.getBoundingClientRect();
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      const next = Math.min(MAX_SCALE, Math.max(minScale.current, view.current.scale * factor));
      const ratio = next / view.current.scale;
      // Keep the point under the cursor still: zoom around it, not around the centre.
      const offsetX = event.clientX - rect.left - rect.width / 2;
      const offsetY = event.clientY - rect.top - rect.height / 2;
      view.current = {
        x: offsetX - (offsetX - view.current.x) * ratio,
        y: offsetY - (offsetY - view.current.y) * ratio,
        scale: next,
      };
      repaint();
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });

    wake();

    return () => {
      observer.disconnect();
      onTheme.disconnect();
      canvas.removeEventListener("wheel", onWheel);
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
    };
  }, [applyFit, flyToConcept, repaint, takeCamera, wake]);

  const zoom = (factor: number) => {
    takeCamera();
    const next = Math.min(MAX_SCALE, Math.max(minScale.current, view.current.scale * factor));
    // Around the centre of the frame: the translation scales with the zoom.
    const ratio = next / view.current.scale;
    view.current = { x: view.current.x * ratio, y: view.current.y * ratio, scale: next };
    repaint();
  };

  const relayout = () => {
    if (viewProps.current.mode === "curriculum") {
      const targets = curriculumPositions(graphRef.current, modelRef.current);
      placeBodies((index) => targets[index], true);
      pendingFit.current = true;
      wake();
      return;
    }
    setPlacing(true);
    requestLayout(graphRef.current, null, true)
      .then((layout) => land(layout, true))
      .catch(() => undefined)
      .finally(() => setPlacing(false));
  };

  const toWorld = (event: { clientX: number; clientY: number }) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left - rect.width / 2 - view.current.x) / view.current.scale,
      y: (event.clientY - rect.top - rect.height / 2 - view.current.y) / view.current.scale,
    };
  };

  const detailNow = () =>
    viewProps.current.mode === "force" ? detailAt(view.current.scale) : 1;

  const pick = (event: { clientX: number; clientY: number }) => {
    const detail = detailNow();
    if (detail < UNIT_CLICKS_BELOW) return -1;
    const world = toWorld(event);
    const { degrees } = modelRef.current;
    const { scale } = view.current;
    const list = bodies.current;
    let best = -1;
    let bestDistance = Infinity;
    for (let index = 0; index < list.length; index += 1) {
      const body = list[index];
      const dx = body.x - world.x;
      const dy = body.y - world.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const reach = drawnRadius(degrees[index] ?? 0, scale, detail) + 5 / scale;
      if (distance < reach && distance < bestDistance) {
        best = index;
        bestDistance = distance;
      }
    }
    return best;
  };

  const unitAt = (event: { clientX: number; clientY: number }) => {
    if (viewProps.current.mode !== "force") return null;
    const world = toWorld(event);
    return (
      placement.current.regions.find(
        (region) =>
          world.x >= region.x &&
          world.x <= region.x + region.width &&
          world.y >= region.y &&
          world.y <= region.y + region.height,
      ) ?? null
    );
  };

  const release = () => {
    const state = pointer.current;
    if (state.mode === "node" && bodies.current[state.index]) {
      bodies.current[state.index].pinned = false;
    }
    pointer.current = { mode: "none", index: -1, x: 0, y: 0, moved: 0 };
  };

  const hoveredNode = hovered !== null ? graph.nodes[hovered] : undefined;
  const hoveredGroup = hoveredUnit !== null ? graph.groups[hoveredUnit] : undefined;

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
        role="img"
        aria-label={t("canvas.aria", {
          concepts: plural("canvas.conceptCount", graph.nodes.length),
          units: plural("canvas.unitCount", graph.groups.length),
        })}
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
            const unit = next === null && detailNow() < UNIT_CLICKS_BELOW ? unitAt(event) : null;
            setHoveredUnit(unit ? unit.group : null);
            if (next !== null || unit) {
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
            view.current = { ...view.current, x: view.current.x + deltaX, y: view.current.y + deltaY };
          } else {
            const body = bodies.current[state.index];
            body.x += deltaX / view.current.scale;
            body.y += deltaY / view.current.scale;
            // A body is held by its target: move the target too or it springs back.
            body.tx = body.x;
            body.ty = body.y;
          }
          repaint();
        }}
        onPointerUp={(event) => {
          const state = pointer.current;
          if (state.mode === "node") {
            if (state.moved < 4) {
              const name = graph.nodes[state.index][0];
              if (onPick) onPick(name);
              else {
                pickedHere.current = name;
                onSelect(name);
              }
            }
          } else if (state.mode === "pan" && state.moved < 4) {
            const unit = detailNow() < 0.6 ? unitAt(event) : null;
            if (unit) {
              const target = frameOf({
                minX: unit.x,
                minY: unit.y,
                maxX: unit.x + unit.width,
                maxY: unit.y + unit.height,
              });
              if (target) flyTo(target);
            } else if (!onPick && pick(event) < 0) {
              onSelect(null);
            }
          }
          release();
        }}
        onPointerCancel={release}
        onPointerLeave={() => {
          setHovered(null);
          setHoveredUnit(null);
          if (pointer.current.mode !== "none") release();
        }}
      />

      {placing ? (
        <span className="pointer-events-none absolute left-1/2 top-2 flex -translate-x-1/2 items-center gap-1.5 rounded-md border border-border bg-card/90 px-2 py-1 text-[12px] text-muted-foreground shadow-sm backdrop-blur">
          <Spinner className="size-3" />
          {t("canvas.placing", { concepts: plural("canvas.conceptCount", graph.nodes.length) })}
        </span>
      ) : null}

      {/* `contents` and not a wrapper with a box: the chrome below is positioned against the
          canvas itself, so anything that generated one would become its containing block and
          move all of it. `hidden` takes the whole subtree out, tab order included. */}
      <div className={compact ? "hidden" : "contents"}>

      <div className="pointer-events-auto absolute left-2 top-2 flex items-center gap-1 rounded-md border border-border bg-card/90 p-0.5 shadow-sm backdrop-blur">
        {(
          [
            {
              value: "force",
              label: t("canvas.layout.force"),
              icon: Network,
              hint: t("canvas.layout.force.hint"),
            },
            {
              value: "curriculum",
              label: t("canvas.layout.curriculum"),
              icon: Waypoints,
              hint: model.curriculumEdges
                ? t("canvas.layout.curriculum.hint", {
                    n: plural("canvas.relations", model.curriculumEdges),
                  })
                : t("canvas.layout.curriculum.none"),
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
              "flex items-center gap-1.5 rounded px-2 py-1 text-small font-medium transition-colors disabled:opacity-40",
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
        <Button variant="secondary" size="icon-sm" onClick={() => zoom(1.2)} aria-label={t("canvas.zoomIn")}>
          <ZoomIn />
        </Button>
        <Button variant="secondary" size="icon-sm" onClick={() => zoom(1 / 1.2)} aria-label={t("canvas.zoomOut")}>
          <ZoomOut />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={fit}
          aria-label={t("canvas.fit")}
          title={t("canvas.fitHint")}
        >
          <Maximize2 />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={relayout}
          disabled={placing}
          aria-label={t("canvas.relayout")}
          title={t("canvas.relayoutHint")}
        >
          <RotateCw />
        </Button>
        <Button
          variant={labels === "none" ? "outline" : "secondary"}
          size="icon-sm"
          onClick={() => setLabels(labels === "auto" ? "all" : labels === "all" ? "none" : "auto")}
          aria-label={t("canvas.labels")}
          title={
            labels === "auto"
              ? t("canvas.labels.auto")
              : labels === "all"
                ? t("canvas.labels.all")
                : t("canvas.labels.none")
          }
        >
          <Tag />
        </Button>
      </div>

      <div className="pointer-events-none absolute bottom-2 left-2 flex flex-col gap-1">
        <button
          type="button"
          onClick={() => setArrows(!arrows)}
          className="pointer-events-auto w-fit rounded-md border border-border bg-card/90 px-2 py-1 text-[12px] text-muted-foreground shadow-sm backdrop-blur transition-colors hover:text-foreground"
        >
          {arrows ? t("canvas.hideArrows") : t("canvas.showArrows")}
        </button>
        <span className="w-fit rounded-md border border-border bg-card/90 px-2 py-1 text-[12px] text-muted-foreground shadow-sm backdrop-blur">
          {plural("canvas.conceptCount", graph.nodes.length)} ·{" "}
          {plural("canvas.relations", graph.links.length)}
          {graph.meta.isolated > 0 ? plural("canvas.isolatedCount", graph.meta.isolated) : ""}
        </span>

        {/* Without a key, three colours on a canvas are three colours. */}
        {mode === "curriculum" && curriculumIndices ? (
          <span className="flex w-fit items-center gap-3 rounded-md border border-border bg-card/90 px-2 py-1 text-[12px] text-muted-foreground shadow-sm backdrop-blur">
            {(
              [
                [t("canvas.legend.covered"), "var(--settled)", curriculumIndices.size],
                [t("canvas.legend.frontier"), "var(--attention)", frontier?.size ?? 0],
                [
                  t("canvas.legend.notTaught"),
                  "var(--muted-foreground)",
                  graph.nodes.length - curriculumIndices.size - (frontier?.size ?? 0),
                ],
              ] as const
            ).map(([label, colour, count]) => (
              <span key={label} className="flex items-center gap-1.5">
                <span className="size-2 rounded-full" style={{ background: colour }} />
                {label} <span className="nums">{count}</span>
              </span>
            ))}
          </span>
        ) : null}
      </div>

      {/* A graph with few prerequisites piles almost everything on level 0. That is a fact about
          the graph, not a failure of the view: saying so keeps it from looking like the latter. */}
      {mode === "curriculum" && model.levelCount < 3 ? (
        <p className="pointer-events-none absolute left-1/2 top-12 max-w-md -translate-x-1/2 rounded-md border border-[color-mix(in_oklch,var(--attention)_40%,transparent)] bg-[color-mix(in_oklch,var(--attention)_12%,var(--card))] px-3 py-1.5 text-center text-[12px] shadow-sm">
          {t("canvas.flatWarning", {
            edges: plural("canvas.relations", model.curriculumEdges),
            concepts: plural("canvas.conceptCount", graph.nodes.length),
          })}
        </p>
      ) : null}

      </div>

      {hoveredNode ? (
        <div
          className="pointer-events-none absolute z-10 max-w-64 rounded-md border border-border bg-popover/95 px-2 py-1 text-small shadow-lg backdrop-blur"
          style={{
            left: Math.min(tip.x + 14, Math.max(0, size.current.width - 260)),
            top: Math.max(4, tip.y - 46),
          }}
        >
          <p className="font-medium">{hoveredNode[0]}</p>
          <p className="text-muted-foreground">
            {t("canvas.degree", {
              domain: graph.groups[hoveredNode[1]]?.name ?? "",
              degree: model.degrees[hovered!] ?? 0,
            })}
            {mode === "curriculum" && model.curriculumEdges > 0
              ? t("canvas.level", { n: model.levels[hovered!] })
              : ""}
          </p>
          {hoveredNode[2] ? (
            <p className="text-muted-foreground">{t("canvas.notTaggable")}</p>
          ) : null}
        </div>
      ) : hoveredGroup ? (
        <div
          className="pointer-events-none absolute z-10 max-w-64 rounded-md border border-border bg-popover/95 px-2 py-1 text-small shadow-lg backdrop-blur"
          style={{
            left: Math.min(tip.x + 14, Math.max(0, size.current.width - 260)),
            top: Math.max(4, tip.y - 46),
          }}
        >
          <p className="font-medium">{hoveredGroup.name}</p>
          <p className="text-muted-foreground">{plural("canvas.conceptCount", hoveredGroup.count)}</p>
          <p className="text-muted-foreground">{t("canvas.unitZoom")}</p>
        </div>
      ) : null}
    </div>
  );
}
