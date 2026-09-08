/* The evaluation's own types: the three arms, one blind session — the system against ONE
 * rival drawn by the seed, on two cards since 2026-09-08 — and what the administration
 * panel reads over the population of them. They live here rather than in `lib/types.ts`
 * for the same reason the Python does: the evaluation is measured against the system, not part
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
  /** Revealed-only, like everything past `item`: what a proposal is about is a quality
   *  signal, and handing it over while the cards are blind judges them for the evaluator. */
  tagging?: ProposalTagging | null;
}

/**
 * What the graph makes of one proposal, run over the three alike after they are all in.
 *
 * `off_limits` is what the proposal brought in from the set the commission put out of
 * bounds — the very block the system arm's prompt carries — so the same rule is applied to
 * all three even though only one was told about it. Under `"mentions"` a concept counts
 * whether the tagger says the exercise is ABOUT it or the text merely NAMES it, so it may
 * not be among `concepts`; under `"practises"` only the primary concept can be there.
 * Absent on an arm that produced no item, and on a session recorded before the pass.
 */
export type ClosureRule = "mentions" | "practises";

export interface ProposalTagging {
  concepts: string[];
  primary: string | null;
  rule?: ClosureRule;
  off_limits: string[];
}

export type Usability = "as_is" | "with_edits" | "no";

/** Ordinal, best first. Neutral keys because a teacher and a student are not asked the
 *  same question: `as_is` would be a lie in a student's row. */
export type TriageValue = "yes" | "partly" | "no";

/* The profile is a property of the ACCOUNT — set when it comes into existence, read here —
 * so its type sits with the account's, exactly as `EVALUATOR_PROFILES` sits in
 * `server/db/models.py` and not in `evaluation/`. */
export type { EvaluatorProfile };

/**
 * What this account is asked, served by the API rather than written here.
 *
 * The wording IS the instrument: rewording it changes what was measured, so it lives in
 * `evaluation/api/instruments.py` and arrives with the listing.
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
  prerequisites?: number;
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
   *  evaluator actually saw. Keys are "1" | "2" — "3" on a session recorded with three. */
  triage: Record<string, TriageValue>;
  choice: number | null;
  choice_arm: EvaluationArm | null;
  chosen_at: number | null;
  /** "No tengo criterio": the session is over and no preference was ever expressed. */
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
 * Who handed it over is deliberately absent: it is recorded and the panel reads it, but on
 * this screen it invites reading the judgement as owed to a person.
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

/** Wilson, so a bound never leaves [0,1] at the extremes the evaluation will actually meet. */
export type Interval = [number, number];

export interface PositionBias {
  cards: number;
  n: number;
  counts: Record<string, number>;
  chi2?: number;
  p: number | null;
}

/**
 * One rival's duel with the system, over the two-card sessions that held that rival.
 *
 * `n` counts every decided one, "ninguna me convence" included, so `share` is the
 * system's share of the answers it got and not of the wins alone; `p` is the exact
 * two-sided binomial against a coin. Null with nothing decided yet.
 */
export interface Duel {
  n: number;
  system: number;
  rival: number;
  none: number;
  share: number | null;
  ci95: Interval | null;
  p: number | null;
}

export interface TriageSlice {
  n: number;
  counts: Record<TriageValue, number>;
  /** "Tal cual" and "con retoques" together: would this save the teacher work at all. */
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
    /** Decided two-card sessions: the ones that enter a duel. */
    n: number;
    expected: number;
    /** Decided sessions recorded with three cards, which enter no duel. */
    legacy: number;
    duels: Partial<Record<EvaluationArm, Duel>>;
  };
  triage: Partial<Record<EvaluationArm, TriageSlice>>;
  /** Did the letter on the card decide anything? Two positions, one degree of freedom —
   *  and, when sessions recorded with three cards exist, those apart under `three_way`. */
  position: PositionBias & { three_way?: PositionBias };
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
 * No `aggregates`: showing somebody the running score of what they are about to judge
 * invites them to even it out. The numbers live in the administration panel.
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

/** One row of the evaluation grouped by something — an account, a workspace. */
export interface AdminGroup extends EvaluationAggregates {
  key: string | number;
  label: string;
  name: string | null;
  /** Optional because an API older than the bundle does not send it. */
  evaluator_profile?: EvaluatorProfile | null;
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
    profile?: EvaluatorProfile | null;
    workspaces: string[];
    /** Every active account of the installation, for the WHO selector. Optional because
     *  an API older than the bundle does not send it, and the selector then only offers
     *  the account already in the filter. */
    accounts?: FilterAccount[];
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
 * offers what the endpoint would refuse; `pending` names the stages still to be approved as
 * ARTIFACT KEYS, which `lib/names.ts` says in the reader's language. Both optional: an
 * older API sends neither, and the panel reads that as offered rather than blocked.
 */
export interface AssignableWorkspace {
  slug: string;
  name: string;
  role: string;
  ready?: boolean;
  pending?: string[];
}

// WHAT A TEACHER ANSWERED ABOUT ONE ARTIFACT ---------------------------------------------
// The shapes `evaluation/api/stage_instruments.py` serves. The wording never lives here: it IS
// the instrument, so it travels from the server and the browser only draws it.

export interface StageQuestionOption {
  value: string;
  label: string;
}

/** One Likert statement: the person says how far they agree with it, on the one scale the
 *  instrument carries. There are no options of its own — the scale is drawn once. */
export interface StageQuestion {
  key: string;
  axis: string;
  statement: string;
  hint?: string;
}

/** The one agreement scale, shared by every statement and by `overall`: `labels[i]` is
 *  the wording of rung `min + i`, and the index IS the score, 5 being best. */
export interface StageScale {
  min: number;
  max: number;
  labels: string[];
}

export interface StageInstrument {
  artifact: string;
  version: string;
  preamble: string;
  /** How many the form asks, `overall` included: the button that OPENS the form says it,
   *  and a constant here would promise a number the instrument does not keep. Optional —
   *  `questionCount()` derives the same number from `questions`. */
  count?: number;
  scale: StageScale;
  questions: StageQuestion[];
  overall: { key: string; axis: string; statement: string };
  note: { key: string; question: string; hint: string };
}

/**
 * How many questions a stage's form asks, `overall` included.
 *
 * The server sends it and this recomputes it for an older API. `overall` counts: it is on
 * the form, it is answered last, and it is what "contestada" means.
 */
export function questionCount(instrument: StageInstrument): number {
  return instrument.count ?? instrument.questions.length + 1;
}

export interface StageAnswers {
  /** One rung of the scale per statement key. */
  answers: Record<string, number>;
  overall: number | null;
  note: string | null;
  /** `overall` is set, which is the last question: the person reached the end. */
  answered: boolean;
  /** Whether this person corrected the artifact before judging it — the evaluation's own
   *  contrast, how the people who corrected rate it against those who did not. `null` is
   *  dijo", which every row written before the question existed carries. */
  curated: boolean | null;
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

// THE CONSTRUCTION FORMS, READ FROM THE PANEL ---------------------------------------------
// The shapes `evaluation/api/stage_store.py` serves over `/api/admin/evaluations/stages`: one
// summary per stage of the chain, one row per evaluator, and every form.

/** One statement of a stage's form, with what everybody answered to it: a count per rung
 *  of the scale, in order, plus any value from an earlier wording under its raw key. The
 *  wording and the rung labels travel from the server: they ARE the instrument. */
export interface StageQuestionSummary {
  key: string;
  axis: string;
  statement: string;
  options: StageQuestionOption[];
  counts: Record<string, number>;
  n: number;
  mean: number | null;
}

export interface StageCurationSlice {
  n: number;
  overall_mean: number | null;
}

export interface StageArtifactSummary {
  artifact: string;
  opened: number;
  answered: number;
  /** The "en conjunto" statement, its mean and a count per rung. */
  overall: { statement: string; n: number; mean: number | null; counts: Record<string, number> };
  questions: StageQuestionSummary[];
  /** "Nada" and "algún retoque" together: the share that leaves the artifact usable. */
  usable: number | null;
  /** The contrast the `curated` column exists for; `unknown` predates the question. */
  curation: Record<"yes" | "no" | "unknown", StageCurationSlice>;
  seconds: { n: number; median: number | null };
  instruments: Record<string, number>;
  notes: number;
}

export interface StageAccountGroup {
  key: string | number;
  label: string;
  name: string | null;
  evaluator_profile: EvaluatorProfile | null;
  opened: number;
  answered: number;
  overall_mean: number | null;
  per_artifact: Record<string, number>;
  curated: number;
  last_at: number;
}

export interface AdminStageRow {
  id: number;
  created_at: number;
  updated_at: number | null;
  seconds: number | null;
  workspace: string | null;
  account: string | null;
  account_id: number | null;
  evaluator_profile: EvaluatorProfile | null;
  artifact: string;
  instrument: string;
  answers: Record<string, string>;
  overall: number | null;
  curated: boolean | null;
  answered: boolean;
  note: string | null;
}

export interface AdminStageEvaluations {
  aggregates: {
    rows: number;
    answered: number;
    opened_only: number;
    overall_mean: number | null;
    by_artifact: StageArtifactSummary[];
  };
  by_account: StageAccountGroup[];
  rows: AdminStageRow[];
}

/** One account the panel can narrow the reading to. */
export interface FilterAccount {
  id: number;
  username: string;
  name: string;
  evaluator_profile: EvaluatorProfile | null;
}

/** The three ways the panel narrows a reading: WHO, which kind of who, and WHERE. */
export interface EvaluationFilters {
  workspace?: string | null;
  account?: number | null;
  profile?: EvaluatorProfile | null;
}
