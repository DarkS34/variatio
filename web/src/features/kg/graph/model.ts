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
  /** Domain index of each node, flattened out of `graph.nodes` for the hot loops. */
  groupOf: number[];
  groupCount: number;
  /** Members of each domain, in node order. Empty domains keep their empty slot. */
  domainMembers: number[][];
  /** Nodes no relation ever mentions. They are laid out apart — see `layout.parkPositions`. */
  isolated: number[];
  /** Prerequisite depth: 0 is "nothing has to be learned first". */
  levels: number[];
  levelCount: number;
  /** Index into `graph.relations` of the prerequisite relation, when the KG has one. */
  prerequisite: number | null;
  /** How many edges actually order the curriculum view. Zero disables it. */
  curriculumEdges: number;
}

// A budget, not a rule: labels are dropped on collision anyway, so this only decides how
// many are *offered*. 16 over 353 concepts left the graph anonymous — you could see the
// shape of the thing and read none of it.
const HUB_LABELS = 34;

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

  const groupCount = Math.max(1, graph.groups.length);
  const groupOf = graph.nodes.map(([, group]) => group);
  const domainMembers: number[][] = Array.from({ length: groupCount }, () => []);
  const isolated: number[] = [];
  for (let index = 0; index < count; index += 1) {
    domainMembers[groupOf[index]]?.push(index);
    if (degrees[index] === 0) isolated.push(index);
  }

  // One colour string per domain and per relation, built once: producing them inside
  // the draw loop meant hundreds of template strings a frame for a dozen values.
  const domainColours = graph.groups.map((_, index) => domainColour(index, graph.groups.length));
  const relationColours = graph.relations.map((relation, index) =>
    relationColour(relation.type ?? relation.key, index),
  );

  // A graph with no labels is a constellation. The hubs get theirs permanently — they
  // are what you navigate by — and every domain contributes its own biggest concept even
  // if it never makes the global cut, so no region of the map is left unnamed.
  const byDegree = [...Array(count).keys()].sort((a, b) => degrees[b] - degrees[a]);
  const hubs = new Set(byDegree.slice(0, HUB_LABELS).filter((index) => degrees[index] > 1));
  for (const members of domainMembers) {
    const best = members.reduce(
      (top, index) => (top < 0 || degrees[index] > degrees[top] ? index : top),
      -1,
    );
    if (best >= 0 && degrees[best] > 1) hubs.add(best);
  }

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
    groupOf,
    groupCount,
    domainMembers,
    isolated,
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
