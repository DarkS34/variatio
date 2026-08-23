/* The study's own types: the three arms, one blind session, and what the administration
 * panel reads over the population of them. They live here rather than in `lib/types.ts`
 * for the same reason the Python does: the study is measured against the system, not part
 * of it. `lib/types.ts` keeps only the two counters the admin overview prints. */

/* Evaluation ----------------------------------------------------------------------- */

export type EvaluationArm = "naive" | "rag" | "system";

export type ArmStatus = "ok" | "failed" | "unavailable";

/**
 * One proposal, as the server chooses to describe it.
 *
 * Before the choice everything past `item` is absent — and that is not the client being
 * polite: the server never sends it. `status` is narrowed to "ok" | "no_item" too,
 * because "unavailable" would point at the commercial arm before a card is read.
 */
export interface EvaluationPosition {
  position: number;
  status: ArmStatus | "no_item";
  item: Record<string, unknown> | null;
  arm?: EvaluationArm;
  arm_label?: string;
  model?: string;
  provider?: string;
  prompt?: string;
  raw_response?: string;
  exemplar_ids?: string[];
  elapsed_ms?: number;
  error?: string | null;
}

export type Usability = "as_is" | "with_edits" | "no";

export interface EvaluationRating {
  arm: string;
  originality?: number;
  complexity?: number;
  concept_fit?: number;
  soundness?: number;
  usability?: Usability;
  comment?: string;
  rated_at?: number;
}

export interface EvaluationSessionHead {
  id: string;
  created_at: number;
  job_id: string | null;
  concepts: string[];
  item_type: string;
  fixed: Record<string, unknown>;
  curriculum: string[];
  instructions: string;
  revealed: boolean;
  choice: number | null;
  choice_arm: EvaluationArm | null;
  chosen_at: number | null;
  evaluator_note: string | null;
  rating: EvaluationRating | null;
  seed: number | null;
  /** Drawn from the seed, never chosen; null until the session is revealed. */
  think: boolean | null;
}

export interface EvaluationDetail {
  session: EvaluationSessionHead;
  positions: EvaluationPosition[];
}

export interface EvaluationSummary {
  id: string;
  created_at: number;
  concepts: string[];
  item_type: string;
  instructions: string;
  choice: number | null;
  choice_arm: EvaluationArm | null;
  chosen_at: number | null;
  rated: boolean;
  /** Empty until the session is judged: before that it would name the blind cards. */
  arm_status: Partial<Record<EvaluationArm, ArmStatus>>;
  without_item: number;
  /** Withheld (null) while the session is pending, like `arm_status`. */
  think: boolean | null;
}

export interface EvaluationRubricSummary {
  n: number;
  usability?: Record<Usability, number>;
  [dimension: string]: any;
}

/** One side of the reasoning draw: the sessions that ran with it on, or with it off. */
export interface ThinkSlice {
  decided: number;
  preferences: Record<string, number>;
  elapsed_ms: Partial<Record<EvaluationArm, number>>;
  rubric: EvaluationRubricSummary;
}

export interface EvaluationAggregates {
  sessions: number;
  decided: number;
  rated: number;
  preferences: Record<string, number>;
  arm_status: Record<string, Record<string, number>>;
  rubric: EvaluationRubricSummary;
  think: { on: ThinkSlice; off: ThinkSlice };
  elapsed_ms: Partial<Record<EvaluationArm, number>>;
}

/**
 * The evaluator's own sessions and nothing else.
 *
 * `aggregates` is deliberately gone from this payload: showing somebody the running score
 * of the thing they are about to judge invites them to even it out. The study's numbers
 * live in the administration panel, over `AdminEvaluations`.
 */
export interface EvaluationListing {
  sessions: EvaluationSummary[];
  total: number;
  limit: number;
  offset: number;
  arms: { key: EvaluationArm; label: string }[];
  external: { provider: string; model: string; configured: boolean; reason: string | null };
}

export interface EvaluationParams {
  concepts: string[];
  item_type?: string;
  fixed?: Record<string, unknown>;
  curriculum?: string[];
  instructions?: string;
}

/** One row of the study grouped by something — an account, a workspace. */
export interface AdminGroup extends EvaluationAggregates {
  key: string | number;
  label: string;
  name: string | null;
  last_at: number;
}

export interface AdminSessionRow {
  id: string;
  created_at: number;
  workspace: string | null;
  account: string | null;
  account_id: number | null;
  concepts: string[];
  item_type: string;
  choice: number | null;
  choice_arm: EvaluationArm | null;
  chosen_at: number | null;
  think: boolean;
  rating: EvaluationRating | null;
  arm_status: Partial<Record<EvaluationArm, ArmStatus>>;
  arm_elapsed_ms: Partial<Record<EvaluationArm, number>>;
  evaluator_note: string | null;
}

export interface AdminEvaluations {
  aggregates: EvaluationAggregates;
  by_account: AdminGroup[];
  by_workspace: AdminGroup[];
  per_day: { day: string; sessions: number; decided: number }[];
  arms: { key: EvaluationArm; label: string }[];
  filters: {
    workspace: string | null;
    account: number | null;
    workspaces: string[];
  };
  sessions: AdminSessionRow[];
}
