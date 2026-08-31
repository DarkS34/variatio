/* The study's own types: the three arms, one blind session, and what the administration
 * panel reads over the population of them. They live here rather than in `lib/types.ts`
 * for the same reason the Python does: the study is measured against the system, not part
 * of it. `lib/types.ts` keeps only the two counters the admin overview prints. */

import type { EvaluatorProfile, ItemChecks } from "@/lib/types";

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
  checks?: ItemChecks | null;
  retried?: number;
}

export type Usability = "as_is" | "with_edits" | "no";

/** Ordinal, best first. Neutral keys because a teacher and a student are not asked the
 *  same question: `as_is` would be a lie in a student's row. */
export type TriageValue = "yes" | "partly" | "no";

/* The profile is a property of the ACCOUNT — set when it comes into existence, read here —
 * so its type sits with the account's, exactly as `EVALUATOR_PROFILES` sits in
 * `server/db/models.py` and not in `study/`. */
export type { EvaluatorProfile };

/**
 * What this account is asked, served by the API rather than written here.
 *
 * The wording IS the instrument: rewording it changes what was measured, so it lives in
 * `study/api/instruments.py` and arrives with the listing. A second copy in the browser
 * is a second thing to keep in step with the analysis.
 */
export interface Instruments {
  profile: EvaluatorProfile;
  triage: {
    question: string;
    hint: string;
    options: { value: TriageValue; label: string }[];
  };
  rubric: {
    key: string;
    label: string;
    question: string;
    ends: [string, string];
    /** Set only where the best answer is the MIDDLE — `complexity`, whose target is 3. */
    target: number | null;
  }[];
  decline: { label: string; hint: string };
}

export interface EvaluationRating {
  arm: string;
  originality?: number;
  complexity?: number;
  concept_fit?: number;
  soundness?: number;
  /** Legacy: the question moved to the blind per-card triage. Old sessions keep theirs. */
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
  /** Somebody handed this session over, rather than the evaluator commissioning it. */
  assigned: boolean;
  /** Answered blind, one per POSITION — never per arm, because a position is what the
   *  evaluator actually saw. Keys are "1" | "2" | "3". */
  triage: Record<string, TriageValue>;
  choice: number | null;
  choice_arm: EvaluationArm | null;
  chosen_at: number | null;
  /** «No tengo criterio»: the session is over and no preference was ever expressed. */
  declined_at: number | null;
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
  assigned: boolean;
  choice: number | null;
  choice_arm: EvaluationArm | null;
  chosen_at: number | null;
  declined_at: number | null;
  rated: boolean;
  /** Empty until the session is judged: before that it would name the blind cards. */
  arm_status: Partial<Record<EvaluationArm, ArmStatus>>;
  without_item: number;
  /** Withheld (null) while the session is pending, like `arm_status`. */
  think: boolean | null;
}

/**
 * One entry of the queue: what somebody handed this evaluator.
 *
 * Who handed it over is deliberately absent — it is recorded and the administration panel
 * reads it, but on this screen it would invite reading the judgement as owed to a person
 * rather than to the study.
 */
export interface QueueItem {
  id: string;
  created_at: number;
  concepts: string[];
  item_type: string;
  instructions: string;
  decided: boolean;
  declined: boolean;
  rated: boolean;
}

export interface EvaluationQueue {
  total: number;
  pending: number;
  items: QueueItem[];
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

/** Wilson, so a bound never leaves [0,1] at the extremes the study will actually meet. */
export type Interval = [number, number];

export interface ArmSignificance {
  wins: number;
  share: number | null;
  ci95: Interval | null;
  /** Exact two-sided binomial against 1/3. Null with nothing decided yet. */
  p: number | null;
}

export interface TriageSlice {
  n: number;
  counts: Record<TriageValue, number>;
  /** «Tal cual» and «con retoques» together: would this save the teacher work at all. */
  usable: number;
  outright: number;
  ci95_usable: Interval | null;
}

/** Pooled over evaluator pairs sharing a set, so the chance term is a single pooled
 *  marginal: Scott's π rather than Cohen's κ proper. The memoria has to say so. */
export interface AgreementSlice {
  pairs: number;
  observed?: number;
  expected?: number;
  kappa?: number | null;
}

export interface EvaluationAggregates {
  sessions: number;
  decided: number;
  declined: number;
  rated: number;
  preferences: Record<string, number>;
  arm_status: Record<string, Record<string, number>>;
  rubric: EvaluationRubricSummary;
  think: { on: ThinkSlice; off: ThinkSlice };
  elapsed_ms: Partial<Record<EvaluationArm, number>>;
  significance: {
    n: number;
    expected: number;
    arms: Record<string, ArmSignificance>;
  };
  triage: Partial<Record<EvaluationArm, TriageSlice>>;
  /** Did the letter on the card decide anything? Three positions, two degrees of freedom. */
  position: {
    n: number;
    counts: Record<string, number>;
    chi2?: number;
    p: number | null;
  };
  duration: {
    n: number;
    median?: number;
    fastest?: number;
    slowest?: number;
    under_20s?: number;
  };
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
  /** What somebody handed this evaluator: the screen opens on it. */
  queue: EvaluationQueue;
  instruments: Instruments;
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
  evaluator_profile: EvaluatorProfile | null;
  set_id: string | null;
  assigned: boolean;
  concepts: string[];
  item_type: string;
  triage_arm: Partial<Record<EvaluationArm, TriageValue>>;
  choice: number | null;
  choice_arm: EvaluationArm | null;
  chosen_at: number | null;
  declined_at: number | null;
  seconds: number | null;
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
  /** Teachers and students counted apart: they were not even asked the same question. */
  by_profile: AdminGroup[];
  agreement: {
    sets_shared: number;
    choice: AgreementSlice;
    triage: AgreementSlice;
  };
  per_day: { day: string; sessions: number; decided: number }[];
  arms: { key: EvaluationArm; label: string }[];
  filters: {
    workspace: string | null;
    account: number | null;
    workspaces: string[];
  };
  sessions: AdminSessionRow[];
}

/* Handing sets out ------------------------------------------------------------------ */

export interface SetHolder {
  session_id: string;
  account_id: number | null;
  account: string | null;
  evaluator_profile: EvaluatorProfile | null;
  assigned: boolean;
  decided: boolean;
  declined: boolean;
}

export interface EvaluationSet {
  set_id: string;
  created_at: number;
  concepts: string[];
  item_type: string;
  instructions: string;
  think: boolean;
  holders: SetHolder[];
}

export interface WorkspaceMember {
  id: number;
  username: string;
  name: string;
  evaluator_profile: EvaluatorProfile | null;
  role: string;
}

export interface AdminSets {
  workspace: string;
  members: WorkspaceMember[];
  sets: EvaluationSet[];
}

/** One candidate evaluator, with the instances they can actually open. Handing somebody a
 *  set of a workspace they are not a member of makes a queue entry that 404s. */
export interface AssignableAccount {
  id: number;
  username: string;
  name: string;
  evaluator_profile: EvaluatorProfile | null;
  is_admin: boolean;
  workspaces: AssignableWorkspace[];
}

/**
 * One instance this account can open, and whether anything can be commissioned in it.
 *
 * `ready` is the same gate `POST /evaluations/generate` enforces, so the screen never
 * offers what the endpoint would refuse; `pending` names the stages still to be approved
 * as ARTIFACT KEYS, which `lib/names.ts` says in the reader's own language rather than
 * the API's. Both are optional because an API older than this bundle sends neither, and
 * the panel reads that as «no lo sabe» — offered, not blocked.
 */
export interface AssignableWorkspace {
  slug: string;
  name: string;
  role: string;
  ready?: boolean;
  pending?: string[];
}

// WHAT A TEACHER ANSWERED ABOUT ONE ARTIFACT ---------------------------------------------
// The shapes `study/api/stage_instruments.py` serves. The wording never lives here: it IS
// the instrument, so it travels from the server and the browser only draws it.

export interface StageQuestionOption {
  value: string;
  label: string;
}

export interface StageQuestion {
  key: string;
  question: string;
  hint?: string;
  options?: StageQuestionOption[];
}

export interface StageInstrument {
  artifact: string;
  version: string;
  preamble: string;
  questions: StageQuestion[];
  overall: {
    key: string;
    question: string;
    scale: { min: number; max: number; ends: string[] };
  };
  note: { key: string; question: string; hint: string };
}

export interface StageAnswers {
  answers: Record<string, string>;
  overall: number | null;
  note: string | null;
  /** `overall` is set, which is the last question: the person reached the end. */
  answered: boolean;
  instrument: string;
  updated_at: string | null;
}

export interface StageReview {
  artifact: string;
  /** Nothing to judge until something is built, and the form has to be able to say so. */
  built: boolean;
  hash: string | null;
  instrument: StageInstrument;
  mine: StageAnswers | null;
}
