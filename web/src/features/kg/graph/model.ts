import { domainColour, relationColour } from "@/lib/format";
import type { GraphView } from "@/lib/types";

/**
 * Everything about the graph that does not change while it is being looked at.
 *
 * Derived once per graph and read on every frame, so nothing here may allocate:
 * the draw loop indexes into these arrays and must never rebuild them.
 */
export interface GraphModel {
  degrees: number[];
  adjacency: Map<number, Set<number>>;
  nameIndex: Map<string, number>;
  domainColours: string[];
  relationColours: string[];
  hubs: Set<number>;
  /** Prerequisite depth: 0 is "nothing has to be learned first". */
  levels: number[];
  levelCount: number;
  /** Index into `graph.relations` of the prerequisite relation, when the KG has one. */
  prerequisite: number | null;
  /** How many edges actually order the curriculum view. Zero disables it. */
  curriculumEdges: number;
}

const HUB_LABELS = 16;

export function buildModel(graph: GraphView): GraphModel {
  const count = graph.nodes.length;
  const degrees = new Array<number>(count).fill(0);
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

  // One colour string per domain and per relation, built once: producing them inside
  // the draw loop meant hundreds of template strings a frame for a dozen values.
  const domainColours = graph.groups.map((_, index) => domainColour(index, graph.groups.length));
  const relationColours = graph.relations.map((relation, index) =>
    relationColour(relation.type ?? relation.key, index),
  );

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

  const prerequisite =
    graph.meta.prerequisite ?? graph.relations.findIndex((relation) => relation.prerequisite);
  const relationIndex = prerequisite === undefined || prerequisite < 0 ? null : prerequisite;
  const { levels, levelCount, edges } = prerequisiteLevels(graph, relationIndex);

  return {
    degrees,
    adjacency,
    nameIndex,
    domainColours,
    relationColours,
    hubs,
    levels,
    levelCount,
    prerequisite: relationIndex,
    curriculumEdges: edges,
  };
}

/**
 * How deep each concept sits in the prerequisite chain.
 *
 * `A tiene como prerrequisito B` points at what must come FIRST, so a concept's depth
 * is one more than the deepest thing it depends on. Depth 0 is therefore the entry
 * point of the syllabus — including every concept the relation never mentions, which
 * is the honest answer: the graph claims nothing has to precede it.
 *
 * The KG is checked for cycles at load, but a hand-edited one can still carry one;
 * the visited guard makes a cycle cost a wrong level rather than a hung tab.
 */
function prerequisiteLevels(
  graph: GraphView,
  relation: number | null,
): { levels: number[]; levelCount: number; edges: number } {
  const count = graph.nodes.length;
  const levels = new Array<number>(count).fill(0);
  if (relation === null) return { levels, levelCount: 1, edges: 0 };

  const requires = new Map<number, number[]>();
  let edges = 0;
  for (const [source, target, kind] of graph.links) {
    if (kind !== relation) continue;
    if (!requires.has(source)) requires.set(source, []);
    requires.get(source)!.push(target);
    edges += 1;
  }
  if (edges === 0) return { levels, levelCount: 1, edges };

  const state = new Uint8Array(count);
  const depth = (node: number): number => {
    if (state[node] === 2) return levels[node];
    if (state[node] === 1) return 0;
    state[node] = 1;
    let best = 0;
    for (const prior of requires.get(node) ?? []) {
      best = Math.max(best, depth(prior) + 1);
    }
    levels[node] = best;
    state[node] = 2;
    return best;
  };

  for (let index = 0; index < count; index += 1) depth(index);
  return { levels, levelCount: Math.max(...levels) + 1, edges };
}
