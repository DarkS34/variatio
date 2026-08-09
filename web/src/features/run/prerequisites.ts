import type { GraphView } from "@/lib/types";

/**
 * The same two hops the generator computes server-side, read off the graph payload.
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

function hop(adj: Adjacency, concepts: string[], edges: Edges): string[] {
  const targets = new Set(concepts);
  const found = new Set<string>();
  for (const concept of concepts) {
    const from = adj.index.get(concept);
    if (from === undefined) continue;
    for (const to of edges.get(from) ?? []) {
      const name = adj.names[to];
      if (name && !targets.has(name)) found.add(name);
    }
  }
  return [...found].sort((a, b) => a.localeCompare(b, "es"));
}

/** One hop out: what the graph says the student already masters. */
export function priors(adj: Adjacency, concepts: string[]): string[] {
  return hop(adj, concepts, adj.out);
}

/** One hop in: downstream of the target, so not taught yet. */
export function posteriors(adj: Adjacency, concepts: string[]): string[] {
  return hop(adj, concepts, adj.in);
}

/**
 * Everything reachable outwards, targets included: a curriculum proposal.
 *
 * Traversal crosses non-taggable concepts but never returns them: the graph carries every
 * concept it extracted, while a curriculum is validated against the taggable set alone
 * (`ContentGenerator._validate_input`). Cutting the walk at them instead of filtering the
 * result would drop whatever legitimately sits behind one.
 */
export function priorClosure(adj: Adjacency, concepts: string[]): string[] {
  const seen = new Set<number>();
  const queue: number[] = [];
  for (const concept of concepts) {
    const start = adj.index.get(concept);
    if (start !== undefined && !seen.has(start)) {
      seen.add(start);
      queue.push(start);
    }
  }
  while (queue.length > 0) {
    for (const next of adj.out.get(queue.pop()!) ?? []) {
      if (seen.has(next)) continue;
      seen.add(next);
      queue.push(next);
    }
  }
  return [...seen]
    .filter((i) => adj.taggable[i])
    .map((i) => adj.names[i])
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b, "es"));
}
