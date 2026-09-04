import { useEffect, useMemo, useRef } from "react";

import { buildModel } from "@/features/kg/graph/model";
import { relationColour } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { GraphView } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * One concept's relations as horizontal flows, one band per relation type.
 *
 * It answers the questionnaire's «¿tiene sentido el orden?» for ONE concept without
 * asking anybody to read the whole graph (2026-09-04, explicit user request; the bands
 * and the other relation types the same day). Every band is a horizontal flow with the
 * concept in the same column, so the three read as one node seen through three
 * relations, and the bands are stacked in a fixed order — the prerequisite first, because
 * it is the one that says «antes de», then the hierarchy, then whatever else the schema
 * declares — with a rule between them. Colours are the canvas's own: a node in its unit's
 * colour, an edge in its relation's.
 *
 * Two reading rules, and they differ on purpose. In the PREREQUISITE band the flow is the
 * order of learning: left of the concept what has to be known before it, followed down to
 * the leaves; right of it what leans on it; the axis words say so. In every OTHER band an
 * arrow reads as the sentence «left VERB right» — the in-neighbours (those that VERB this
 * concept) sit left and the out-neighbours (what this concept VERBs) sit right, followed
 * transitively when the relation is directed and one hop when it is not, where a closure
 * over «se relaciona con» would be most of the graph.
 *
 * Layers are BFS distance, one column per layer; the concept's column is the widest left
 * depth over all bands, so it lines up. The drawing takes the width it needs and scrolls
 * inside the card, centred on the concept when it opens, and each band's caption is
 * sticky on the left so the verb is read whatever part of a wide flow is in view.
 */

const ROW = 22;
const R = 5;
const PAD_X = 12;
const PAD_Y = 6;
// Between the end of a column's longest name and the next column's dot.
const GAP = 40;
const FONT_PX = 11;
// Fallback per-glyph width when no 2D context can measure (a test renderer).
const GLYPH = 6;

interface Node {
  index: number;
  name: string;
  col: number;
  row: number;
  colour: string;
  /** The rendered width of the full name, measured — names are never clipped. */
  labelWidth: number;
}

interface Edge {
  from: Node;
  to: Node;
  arrow: boolean;
}

interface Band {
  relation: number;
  label: string;
  colour: string;
  prerequisite: boolean;
  nodes: Node[];
  edges: Edge[];
  rows: number;
}

type Edges = Map<number, number[]>;

function layers(start: number, edges: Edges, maxDepth: number): Map<number, number> {
  const depth = new Map<number, number>();
  const queue = [start];
  depth.set(start, 0);
  while (queue.length > 0) {
    const current = queue.shift()!;
    const d = depth.get(current)!;
    if (d >= maxDepth) continue;
    for (const next of edges.get(current) ?? []) {
      if (depth.has(next)) continue;
      depth.set(next, d + 1);
      queue.push(next);
    }
  }
  depth.delete(start);
  return depth;
}

/**
 * Measure names in the page's own face at the size the SVG draws them. Every name is drawn
 * whole (2026-09-04, explicit user request: «que salgan los nombres completos»), so each
 * column is as wide as its longest name and nothing else decides it.
 */
function measurer(): (text: string) => number {
  if (typeof document === "undefined") return (text) => text.length * GLYPH;
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return (text) => text.length * GLYPH;
  const family = getComputedStyle(document.documentElement).fontFamily || "sans-serif";
  context.font = `${FONT_PX}px ${family}`;
  return (text) => context.measureText(text).width;
}

function push(edges: Edges, from: number, to: number) {
  const bucket = edges.get(from);
  if (bucket) bucket.push(to);
  else edges.set(from, [to]);
}

export function ConceptFlow({
  graph,
  concept,
  onSelect,
  className,
}: {
  graph: GraphView;
  concept: string;
  onSelect?: (name: string) => void;
  className?: string;
}) {
  const { t } = useT();
  const scroller = useRef<HTMLDivElement>(null);

  const scene = useMemo(() => {
    const target = graph.nodes.findIndex(([name]) => name === concept);
    if (target < 0) return null;
    const model = buildModel(graph);
    const names = graph.nodes.map(([name]) => name);
    const measure = measurer();

    // One adjacency per relation, both ways.
    const outBy = new Map<number, Edges>();
    const inBy = new Map<number, Edges>();
    for (const [source, dest, kind] of graph.links) {
      if (!outBy.has(kind)) {
        outBy.set(kind, new Map());
        inBy.set(kind, new Map());
      }
      push(outBy.get(kind)!, source, dest);
      push(inBy.get(kind)!, dest, source);
    }

    // The prerequisite first, then the schema's own order.
    const order = graph.relations
      .map((_, index) => index)
      .sort((a, b) => Number(b === graph.meta.prerequisite) - Number(a === graph.meta.prerequisite));

    type Half = { left: Map<number, number>; right: Map<number, number> };
    const halves = new Map<number, Half>();
    for (const relation of order) {
      const out = outBy.get(relation);
      const incoming = inBy.get(relation);
      if (!out || !incoming) continue;
      const spec = graph.relations[relation];
      const prerequisite = relation === graph.meta.prerequisite;
      const depth = spec.directed ? Infinity : 1;
      let left: Map<number, number>;
      let right: Map<number, number>;
      if (prerequisite) {
        left = layers(target, out, depth);
        right = layers(target, incoming, depth);
      } else if (spec.directed) {
        left = layers(target, incoming, depth);
        right = layers(target, out, depth);
      } else {
        // An undirected relation is a star: every neighbour, whichever side the file
        // wrote it on, one hop to the right.
        left = new Map();
        right = new Map([...layers(target, out, 1), ...layers(target, incoming, 1)]);
      }
      if (left.size + right.size === 0) continue;
      halves.set(relation, { left, right });
    }
    if (halves.size === 0)
      return { bands: [] as Band[], columns: 0, targetCol: 0, target, starts: [] as number[], width: 0 };

    const leftDepth = Math.max(0, ...[...halves.values()].flatMap((h) => [...h.left.values()]));
    const rightDepth = Math.max(0, ...[...halves.values()].flatMap((h) => [...h.right.values()]));
    const targetCol = leftDepth;
    const columns = leftDepth + rightDepth + 1;

    const bands: Band[] = [];
    for (const [relation, { left, right }] of halves) {
      const spec = graph.relations[relation];
      const prerequisite = relation === graph.meta.prerequisite;
      const perColumn = new Map<number, number[]>();
      const place = (index: number, col: number) => {
        const bucket = perColumn.get(col) ?? [];
        bucket.push(index);
        perColumn.set(col, bucket);
      };
      for (const [index, d] of left) place(index, targetCol - d);
      place(target, targetCol);
      for (const [index, d] of right) place(index, targetCol + d);

      const rows = Math.max(...[...perColumn.values()].map((bucket) => bucket.length));
      const nodes = new Map<number, Node>();
      for (const [col, bucket] of perColumn) {
        bucket.sort((a, b) => names[a].localeCompare(names[b], "es"));
        const offset = (rows - bucket.length) / 2;
        bucket.forEach((index, i) => {
          nodes.set(index, {
            index,
            name: names[index],
            col,
            row: offset + i,
            colour: model.domainColours[model.groupOf[index]] ?? "currentColor",
            labelWidth: measure(names[index]),
          });
        });
      }

      // The prerequisite band draws the edge REVERSED — from the prerequisite to what needs
      // it, which is the direction of learning — and every other band draws it as written,
      // so that an arrow there reads «left VERB right».
      const edges: Edge[] = [];
      for (const [source, dest, kind] of graph.links) {
        if (kind !== relation || !nodes.has(source) || !nodes.has(dest)) continue;
        const a = nodes.get(source)!;
        const b = nodes.get(dest)!;
        if (!spec.directed) {
          if (source !== target && dest !== target) continue;
          const other = source === target ? b : a;
          edges.push({ from: nodes.get(target)!, to: other, arrow: false });
        } else if (prerequisite) {
          edges.push({ from: b, to: a, arrow: true });
        } else {
          edges.push({ from: a, to: b, arrow: true });
        }
      }

      bands.push({
        relation,
        label: spec.verbose ?? spec.key,
        colour: relationColour(spec.type ?? spec.key, relation),
        prerequisite,
        nodes: [...nodes.values()],
        edges,
        rows,
      });
    }
    // A column is as wide as the longest name it holds in ANY band, so the concept lines
    // up across bands and no name is cut.
    const widths = new Array<number>(columns).fill(0);
    for (const band of bands)
      for (const node of band.nodes)
        widths[node.col] = Math.max(widths[node.col], R * 2 + 5 + node.labelWidth + GAP);
    const starts: number[] = [];
    let cursor = PAD_X;
    for (const w of widths) {
      starts.push(cursor);
      cursor += w;
    }
    return { bands, columns, targetCol, target, starts, width: cursor + PAD_X };
  }, [graph, concept]);

  const width = scene ? scene.width : 0;
  const x = (col: number) => (scene?.starts[col] ?? 0) + R + 2;
  const y = (row: number) => PAD_Y + row * ROW + ROW / 2;

  // Open on the concept, not on the leaves: the leftmost column of a deep concept can be
  // five columns away from the one that was clicked.
  useEffect(() => {
    const box = scroller.current;
    if (!box || !scene) return;
    box.scrollLeft = Math.max(0, x(scene.targetCol) - box.clientWidth / 2);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene]);

  if (!scene) return null;
  if (scene.bands.length === 0) {
    return <p className={cn("p-3 text-small text-muted-foreground", className)}>{t("kg.flow.none")}</p>;
  }

  return (
    <div
      ref={scroller}
      className={cn(
        "thin-scroll overflow-x-auto rounded-md border border-border bg-background",
        className,
      )}
      aria-label={t("kg.flow.aria", { name: concept })}
    >
      {scene.bands.map((band, position) => {
        const height = PAD_Y * 2 + band.rows * ROW;
        const marker = `concept-flow-arrow-${band.relation}`;
        return (
          <div
            key={band.relation}
            className={cn("py-1", position > 0 && "border-t border-dashed border-border")}
          >
            {/* Sticky on the left: the verb is what makes the band legible, and a wide
                flow is scrolled to its middle. Each caption says how its arrows are read:
                the prerequisite band as the order of learning, every other one as the
                sentence «izquierda VERBO derecha». */}
            <div className="sticky left-0 inline-flex max-w-full items-center gap-2 px-2 pt-0.5 text-small">
              <span className="h-0.5 w-3.5 shrink-0 rounded-full" style={{ background: band.colour }} />
              <span className="whitespace-nowrap font-medium" style={{ color: band.colour }}>
                {band.label}
              </span>
              <span className="text-muted-foreground">
                {band.prerequisite
                  ? t("kg.flow.order")
                  : t("kg.flow.reads", { verb: band.label })}
              </span>
            </div>
            <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block">
              <defs>
                <marker
                  id={marker}
                  viewBox="0 0 8 8"
                  refX="7"
                  refY="4"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M0,0.5 L8,4 L0,7.5 Z" fill={band.colour} />
                </marker>
              </defs>

              {/* Edges first, under the nodes. A cubic between two columns reads as a flow
                  where a straight line through a column of names reads as a scratch. It
                  leaves AFTER the label — ~5.8 px per glyph at 11 px — and lands before
                  the dot. */}
              {band.edges.map((edge, i) => {
                // Two nodes of one column (a hierarchy edge between two things this concept
                // is englobed in, say) get a small arc on their left; a left-to-right cubic
                // between them collapses into a stub with the arrowhead over the name.
                if (edge.to.col === edge.from.col) {
                  const cx = x(edge.from.col);
                  const down = edge.to.row > edge.from.row;
                  const y1 = y(edge.from.row) + (down ? R + 1 : -(R + 1));
                  const y2 = y(edge.to.row) - (down ? R + 1 : -(R + 1));
                  return (
                    <path
                      key={i}
                      d={`M${cx},${y1} C${cx - 16},${y1} ${cx - 16},${y2} ${cx},${y2}`}
                      fill="none"
                      stroke={band.colour}
                      strokeOpacity={0.6}
                      strokeWidth={1.25}
                      markerEnd={edge.arrow ? `url(#${marker})` : undefined}
                    />
                  );
                }
                const forward = edge.to.col > edge.from.col;
                const tail = forward ? edge.from : edge.to;
                const head = forward ? edge.to : edge.from;
                const x1 = x(tail.col) + R + 5 + tail.labelWidth + 3;
                const x2 = x(head.col) - R - 1;
                const y1 = y(tail.row);
                const y2 = y(head.row);
                const mid = (x1 + x2) / 2;
                return (
                  <path
                    key={i}
                    d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`}
                    fill="none"
                    stroke={band.colour}
                    strokeOpacity={0.6}
                    strokeWidth={1.25}
                    markerEnd={edge.arrow && forward ? `url(#${marker})` : undefined}
                    markerStart={edge.arrow && !forward ? `url(#${marker})` : undefined}
                  />
                );
              })}

              {band.nodes.map((node) => {
                const isTarget = node.index === scene.target;
                const cx = x(node.col);
                const cy = y(node.row);
                return (
                  <g
                    key={node.index}
                    className={onSelect && !isTarget ? "cursor-pointer" : undefined}
                    onClick={onSelect && !isTarget ? () => onSelect(node.name) : undefined}
                  >
                    <title>{node.name}</title>
                    {isTarget ? (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={R + 3.5}
                        fill="none"
                        stroke="var(--primary)"
                        strokeWidth={1.5}
                      />
                    ) : null}
                    <circle cx={cx} cy={cy} r={R} fill={node.colour} />
                    <text
                      x={cx + R + 5}
                      y={cy}
                      dominantBaseline="central"
                      fontSize={FONT_PX}
                      fontWeight={isTarget ? 600 : 400}
                      fill={isTarget ? "var(--foreground)" : "var(--muted-foreground)"}
                    >
                      {node.name}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        );
      })}
    </div>
  );
}
