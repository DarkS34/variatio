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
  /** Domain index of each node, flattened out of `graph.nodes` for the hot loops. */
  groupOf: number[];
  groupCount: number;
  /** The links of each relation, as indices into `graph.links`: one pass per colour. */
  linkBuckets: Uint32Array[];
  /**
   * Relations between two different units, counted per pair and busiest first: what the map
   * draws between the regions while it is too far out to draw a concept's own lines.
   */
  unitLinks: [number, number, number][];
  /** Prerequisite depth: 0 is "nothing has to be learned first". */
  levels: number[];
  levelCount: number;
  /** Index into `graph.relations` of the prerequisite relation, when the KG has one. */
  prerequisite: number | null;
  /** How many edges actually order the curriculum view. Zero disables it. */
  curriculumEdges: number;
}

export function buildModel(graph: GraphView): GraphModel {
  const count = graph.nodes.length;
  const degrees = new Array<number>(count).fill(0);
  const adjacency = new Map<number, Set<number>>();

  const buckets: number[][] = graph.relations.map(() => []);
  const pairs = new Map<number, number>();
  const groupCount = Math.max(1, graph.groups.length);
  graph.links.forEach(([source, target, relation], index) => {
    degrees[source] += 1;
    degrees[target] += 1;
    if (!adjacency.has(source)) adjacency.set(source, new Set());
    if (!adjacency.has(target)) adjacency.set(target, new Set());
    adjacency.get(source)!.add(target);
    adjacency.get(target)!.add(source);
    (buckets[relation] ??= []).push(index);
    const a = graph.nodes[source]?.[1];
    const b = graph.nodes[target]?.[1];
    if (a !== undefined && b !== undefined && a !== b) {
      const pair = Math.min(a, b) * groupCount + Math.max(a, b);
      pairs.set(pair, (pairs.get(pair) ?? 0) + 1);
    }
  });

  const nameIndex = new Map<string, number>();
  graph.nodes.forEach(([name], index) => nameIndex.set(name, index));

  const groupOf = graph.nodes.map(([, group]) => group);

  // One colour string per domain and per relation, built once: producing them inside
  // the draw loop meant hundreds of template strings a frame for a dozen values.
  const domainColours = graph.groups.map((_, index) => domainColour(index, graph.groups.length));
  const relationColours = graph.relations.map((relation, index) =>
    relationColour(relation.type ?? relation.key, index),
  );

  const unitLinks = [...pairs]
    .map(([pair, links]): [number, number, number] => [
      Math.floor(pair / groupCount),
      pair % groupCount,
      links,
    ])
    .sort((a, b) => b[2] - a[2]);

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
    groupOf,
    groupCount,
    linkBuckets: buckets.map((bucket) => Uint32Array.from(bucket ?? [])),
    unitLinks,
    levels,
    levelCount,
    prerequisite: relationIndex,
    curriculumEdges: edges,
  };
}

/**
 * How deep each concept sits in the prerequisite chain.
 *
 * `A has B as a prerequisite` points at what must come FIRST, so a concept's depth
 * is one more than the deepest thing it depends on. Depth 0 is therefore the entry
 * point of the syllabus — including every concept the relation never mentions, which
 * is the honest answer: the graph claims nothing has to precede it.
 *
 * The KG is checked for cycles at load, but a hand-edited one can still carry one;
 * the visited guard makes a cycle cost a wrong level rather than a hung tab. The walk is
 * an explicit stack and not recursion: a prerequisite chain a few thousand deep is a
 * stack overflow in a recursive walk, and a 10 000-concept subject can have one.
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
  for (let start = 0; start < count; start += 1) {
    if (state[start] === 2) continue;
    const stack: [number, number][] = [[start, 0]];
    state[start] = 1;
    while (stack.length > 0) {
      const frame = stack[stack.length - 1];
      const [node, next] = frame;
      const priors = requires.get(node) ?? [];
      if (next < priors.length) {
        frame[1] += 1;
        const prior = priors[next];
        if (state[prior] === 0) {
          state[prior] = 1;
          stack.push([prior, 0]);
        }
        continue;
      }
      let best = 0;
      for (const prior of priors) {
        // A prior still on the stack is a cycle: it counts as depth 0, as the recursion did.
        if (state[prior] === 2) best = Math.max(best, levels[prior] + 1);
        else best = Math.max(best, 1);
      }
      levels[node] = best;
      state[node] = 2;
      stack.pop();
    }
  }
  return { levels, levelCount: Math.max(0, ...levels) + 1, edges };
}

/**
 * What can be taught next: not covered, but with every prerequisite already covered.
 *
 * It lives here, next to `prerequisiteLevels`, because both depend on the same convention
 * and getting it backwards fails silently — `A -> B` means "B is a prerequisite of A", so
 * a concept's prerequisites are the TARGETS of its outgoing edges. Read the other way you
 * still get a plausible non-empty set, and the only symptom is a frontier drawn behind the
 * course instead of in front of it.
 */
export function frontierOf(
  graph: GraphView,
  model: GraphModel,
  curriculum: Set<number>,
): Set<number> {
  const frontier = new Set<number>();
  if (model.prerequisite === null || model.curriculumEdges === 0) return frontier;

  const requires = new Map<number, number[]>();
  for (const [source, target, kind] of graph.links) {
    if (kind !== model.prerequisite) continue;
    if (!requires.has(source)) requires.set(source, []);
    requires.get(source)!.push(target);
  }

  for (let index = 0; index < graph.nodes.length; index += 1) {
    if (curriculum.has(index)) continue;
    const priors = requires.get(index);
    // A concept with no prerequisites at all is reachable from the start, so it belongs to
    // the frontier of an empty course too — which is exactly what a first week looks like.
    if ((priors ?? []).every((prior) => curriculum.has(prior))) frontier.add(index);
  }
  return frontier;
}
