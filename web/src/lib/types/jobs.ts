/** The queue: a job, its kinds and states, the lanes it waits on and the events it sends. */

import type { ArtifactName } from "./pipeline";

export type JobKind =
  | "build_profile"
  | "build_kg"
  | "build_bank"
  | "transcribe"
  | "describe_concepts"
  | "index"
  | "tag"
  | "tag_item"
  | "review_taggability"
  | "generate"
  | "evaluate"
  | "tutor_turn"
  | "tutor_criteria"
  | "activity_digest";

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

/**
 * The two queues, one per inference backend: the GPU and the hosted API.
 *
 * A job reserves the lanes of the generative models it calls — the embedder and the
 * guardrail reserve nothing — so two jobs on disjoint lanes run at the same time, and "el
 * motor está ocupado" is never one sentence.
 *
 * A lane has ROOM: local is one job because the GPU is one, remote is
 * `CEREBRAS_MAX_CONCURRENT_JOBS` because what is shared there is a quota the server
 * administers call by call. So `busy` means the lane is FULL, not that something is
 * running on it.
 */
export type LaneName = "local" | "remote";

export interface LaneState {
  /** The lane is FULL: a job arriving now would wait. Not "something is running". */
  busy: boolean;
  /** How many jobs hold it right now, whoever launched them. */
  running: number;
  /** How many fit at once. 1 for the GPU, always. */
  capacity: number;
  /** Whether any of what occupies the lane belongs to this workspace. */
  mine: boolean;
  /**
   * The kind of job that holds it, whoever launched it: the machine is the installation's.
   * Null when nothing does, when the API is older than the field, or when the holder belongs
   * to a function closed to this account.
   */
  kind: string | null;
  /** The server's own name for that job, in the API's language: the fallback for `kind`. */
  label: string | null;
  queued: number;
  /** Jobs before this workspace's first queued one, or null when it has none waiting. */
  ahead: number | null;
}

export type Lanes = Record<LaneName, LaneState>;

export interface Job {
  id: string;
  kind: JobKind;
  workspace: string;
  user_id: number | null;
  user_name: string | null;
  params: Record<string, unknown>;
  status: JobStatus;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  error: string | null;
  /** A stable name for WHY it failed, when the cause declares one (`instructions_blocked`). */
  error_code?: string | null;
  result: Record<string, any> | null;
  label: string;
  artifact: ArtifactName | null;
  elapsed_ms: number | null;
  /** 1-based place in the queue of its own lanes; 0 or absent means "not waiting". */
  queue_position?: number;
  /** The lanes this job reserves. `[]` is a real answer — a job that calls no generative
   *  model waits for nothing — and absent means the API did not say. */
  backends?: LaneName[];
}

export interface VgEvent {
  seq: number;
  ts: number;
  job_id: string | null;
  kind: string;
  [payload: string]: any;
}
