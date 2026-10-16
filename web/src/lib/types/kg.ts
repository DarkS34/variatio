/** Step 2: the syllabus, its concepts and relations, and the course's progress. */

export interface KgConcept {
  name: string;
  domain: string;
  taggable: boolean;
  degree: number;
  description: string | null;
  exemplars: number;
  /** Only the modalities the bank's items declare; an untyped item is in `exemplars` alone. */
  exemplars_by_type: Record<string, number>;
}

export interface KgSummary {
  path: string;
  domains: { name: string; concepts: string[] }[];
  concepts: KgConcept[];
  relations: { name: string; details: Record<string, any>; edges: number }[];
  totals: {
    domains: number;
    concepts: number;
    taggable: number;
    described: number;
    with_exemplars: number;
    taggability_reviewed: boolean;
  };
}

/**
 * Where a concept came from: the literal piece of the theory corpus it appears in.
 *
 * The graph build writes it and the description prompt reads it, so it is also what says
 * whether a description describes the material or what the model already knew.
 */
export interface ConceptSource {
  document: string;
  location: string;
  text: string;
}

export interface GraphRelation {
  /** The verbose label, which is also the name the edit endpoints speak. */
  key: string;
  verbose?: string;
  /** Schema key when the relation is one the builder knows about: what fixes its colour. */
  type?: string;
  directed: boolean;
  acyclic?: boolean;
  use_in_embedding?: boolean;
  prerequisite?: boolean;
  count: number;
}

export interface GraphView {
  meta: {
    title: string;
    kind: string;
    generated: string;
    isolated: number;
    /** Index into `relations` of the prerequisite relation, or null when there is none. */
    prerequisite?: number | null;
  };
  relations: GraphRelation[];
  groups: { name: string; count: number }[];
  /** [name, groupIndex, nonTaggable] */
  nodes: [string, number, number][];
  /** [sourceIndex, targetIndex, relationIndex] */
  links: [number, number, number][];
}

/**
 * `dropped` is computed against the whole graph, not the taggable set: a curriculum
 * declares coverage, so a non-taggable concept in it is legitimate and only a concept
 * the graph no longer has at all stops counting.
 */
export interface CurriculumState {
  concepts: string[];
  updated_at: string | null;
  dropped: string[];
  /** For a group: whether it follows its own progress (true) or the subject's. Absent on an
   *  older API, and for the subject's own. */
  own?: boolean;
}
