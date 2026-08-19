import type { GraphView } from "@/lib/types";

/**
 * The same two closures the generator computes server-side, read off the graph payload.
 *
 * `ContentGenerator._prerequisites()` walks the prerequisite relation OUTwards (what the
 * student is assumed to master already) and `_posteriors()` INwards (not yet taught, and
 * therefore forbidden). Links arrive as `[source, target, relation]`, so an out-neighbour
 * of `c` is the target of a link whose source is `c`. Getting the direction backwards
 * would silently swap "given" and "forbidden" in the UI.
 */
type Edges = Map<number, number[]>;

interface Adjacency {
  out: Edges;
  in: Edges;
  index: Map<string, number>;
  names: string[];
  taggable: boolean[];
}

export function adjacency(graph: GraphView | undefined): Adjacency | null {
  const relation = graph?.meta?.prerequisite;
  if (!graph || relation === null || relation === undefined) return null;

  const push = (edges: Edges, from: number, to: number) => {
    const bucket = edges.get(from);
    if (bucket) bucket.push(to);
    else edges.set(from, [to]);
  };

  const out: Edges = new Map();
  const incoming: Edges = new Map();
  for (const [source, target, kind] of graph.links) {
    if (kind !== relation) continue;
    push(out, source, target);
    push(incoming, target, source);
  }

  const names = graph.nodes.map(([name]) => name);
  const taggable = graph.nodes.map(([, , nonTaggable]) => !nonTaggable);
  return {
    out,
    in: incoming,
    index: new Map(names.map((name, i) => [name, i])),
    names,
    taggable,
  };
}

/**
 * The transitive closure, in whichever direction is asked for. Both sides of the graph
 * reading have been closures since 2026-08-19: at one hop, a concept two steps away was
 * neither allowed nor forbidden, and the forbidden side is the safety-relevant one.
 *
 * `taggableOnly` filters the RESULT without cutting the traversal short: the graph carries
 * every concept it extracted, while a curriculum is validated against the taggable set
 * alone (`ContentGenerator._validate_input`), so stopping at a non-taggable concept would
 * drop whatever legitimately sits behind it.
 */
function closure(
  adj: Adjacency,
  concepts: string[],
  edges: Edges,
  taggableOnly: boolean,
): string[] {
  const start = new Set(concepts);
  const seen = new Set<number>();
  const queue: number[] = [];
  for (const concept of concepts) {
    const index = adj.index.get(concept);
    if (index !== undefined) queue.push(index);
  }
  while (queue.length > 0) {
    for (const next of edges.get(queue.pop()!) ?? []) {
      if (seen.has(next)) continue;
      seen.add(next);
      queue.push(next);
    }
  }
  return [...seen]
    .filter((i) => !taggableOnly || adj.taggable[i])
    .map((i) => adj.names[i])
    .filter((name) => name && !start.has(name))
    .sort((a, b) => a.localeCompare(b, "es"));
}

/** Everything before the target: what the graph says is already mastered. */
export function priors(adj: Adjacency, concepts: string[]): string[] {
  return closure(adj, concepts, adj.out, true);
}

/** Everything after the target: what has not been taught yet. */
export function posteriors(adj: Adjacency, concepts: string[]): string[] {
  return closure(adj, concepts, adj.in, true);
}
