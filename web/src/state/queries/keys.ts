/** The query keys every area shares, and `scoped`, which names one instance in a key. */

export const keys = {
  health: ["health"] as const,
  // Not scoped: the tab's subject, the one `X-Workspace` names.
  curriculum: ["kg", "curriculum"] as const,
  studentUses: ["members", "uses"] as const,
  activity: ["activity"] as const,
  pipeline: ["pipeline"] as const,
  profile: ["profile"] as const,
  context: ["context"] as const,
  kg: ["kg"] as const,
  kgGraph: ["kg", "graph"] as const,
  bank: (params: Record<string, unknown>) => ["bank", params] as const,
  coverage: ["bank", "coverage"] as const,
  jobs: ["jobs"] as const,
  allowance: ["jobs", "allowance"] as const,
  raw: ["raw"] as const,
  // The phase plan of each builder. It is a property of the code, not of the instance, so
  // it is fetched once and never invalidated — nothing a user does can change it.
  phases: ["pipeline", "phases"] as const,
  // Keyed by modality, because the fields a modality declares are half of what decides
  // the owners: two modalities of one instance do not have the same scope.
  scope: (itemType: string) => ["pipeline", "scope", itemType] as const,
  generations: (params: Record<string, unknown>) => ["generations", params] as const,
  generation: (id: string) => ["generations", "one", id] as const,
  workspaces: ["workspaces"] as const,
  // The class of the subject in use: instance data, dropped with the rest on a switch.
  members: ["members"] as const,
  classLink: ["members", "class-link"] as const,
  classLinkUrl: ["members", "class-link", "link"] as const,
  memberInvites: ["members", "invites"] as const,
  adminClassLinks: ["admin", "class-links"] as const,
  adminOverview: ["admin", "overview"] as const,
  adminGenerations: (slug: string, params: Record<string, unknown>) =>
    ["admin", "generations", slug, params] as const,
  adminInvites: ["admin", "invites"] as const,
  adminJobs: ["admin", "jobs"] as const,
  adminJobHistory: ["admin", "jobs", "history"] as const,
  adminEngine: ["admin", "engine"] as const,
  adminFeatures: ["admin", "features"] as const,
  maintenance: ["maintenance"] as const,
  adminMaintenance: ["admin", "maintenance"] as const,
};

/**
 * Every stage questionnaire's form at once: the prefix `consumers/evaluation/queries` keys each
 * form under, and what an artifact write invalidates (`useInvalidateChain`).
 *
 * Here and not in `consumers/evaluation/`, because the chain's invalidation is core and core
 * imports nothing of the evaluation. Invalidating a prefix nothing is cached under costs nothing,
 * so it is the same call with the evaluation closed.
 */
export const stageReviewKeys = ["stage-review"] as const;

/**
 * The three reads a commission is composed from, optionally about a NAMED instance.
 *
 * With a slug it goes into the query key as well as into the header: two instances sharing
 * `["kg"]` would serve one graph as the other's. The base key stays a PREFIX of the named
 * one, so every `invalidateQueries` already written reaches both.
 */
export const scoped = <K extends readonly unknown[]>(key: K, workspace?: string | null) =>
  workspace ? ([...key, workspace] as const) : key;
