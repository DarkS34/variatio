import type { Job, JobStatus } from "@/lib/types";

import type { ConceptMapData } from "./conceptMap";

/** What `/api/tutor` answers before anything else: whether the tutor can answer here at all. */
export interface TutorStatus {
  ready: boolean;
  /** The server's sentence naming the construction steps still open, or null when none is. */
  blocked: string | null;
  criteria: {
    origin: CriteriaOrigin;
    built: CriteriaBuilt | null;
    job: Job | null;
  };
  /** Whether this account's role lets it correct the criteria: a teacher's, never a student's. */
  can_edit: boolean;
}

export type CriteriaOrigin = "curated" | "draft" | "missing";

export interface CriteriaBuilt {
  at?: string;
  model?: string;
  effort?: string | boolean;
  units?: number;
  dropped?: number;
}

export interface Place {
  document: string;
  location: string;
}

export interface ConversationRow {
  id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
  turns: number;
  pending: boolean;
  focus: string[];
}

/** Why a student's message got no reply: its job failed, was stopped, or was lost to a restart. */
export type FailedReason = "failed" | "cancelled" | "interrupted" | string;

export interface StudentTurn {
  role: "student";
  text: string;
  at: string;
  /** The concept the student chose this message to be about, when they chose one. */
  concept?: string;
  failed?: FailedReason;
}

export interface TutorTurn {
  role: "tutor";
  text: string;
  at: string;
  kind?: string;
  references?: Place[];
  card?: { concepts?: string[]; [key: string]: unknown } | null;
  /** The concept map shown under this reply, on the few replies the server gives one. */
  concept_map?: ConceptMapData | null;
  fallback?: boolean;
  retried?: boolean;
}

export type Turn = StudentTurn | TutorTurn;

export interface Pending {
  job_id: string;
  turn: number;
  status: JobStatus | null;
  queue_position: number;
  job: Job | null;
}

export interface Conversation extends Omit<ConversationRow, "turns" | "pending"> {
  opened_from: { kind: "message" } | { kind: "generation"; generation_id: string; concepts?: string[] };
  state: { focus?: string[]; trail?: string[] };
  turns: Turn[];
  pending: Pending | null;
}

/** The conversation, as the routes that change it answer: the record and the job now queued. */
export interface TurnQueued {
  conversation: Conversation;
  job: Job;
}

export type Strength = "must" | "should";

export interface Criterion {
  text: string;
  strength: Strength;
  concepts: string[];
  sources: Place[];
}

export interface ForbiddenTerm {
  term: string;
  reason: string;
  sources: Place[];
}

export interface CriteriaDocument {
  general: Criterion[];
  units: Record<string, Criterion[]>;
  forbidden_terms: ForbiddenTerm[];
  administrative_reply: string;
  built?: CriteriaBuilt;
}

export interface CriteriaPayload {
  origin: CriteriaOrigin;
  criteria: CriteriaDocument;
  warnings: string[];
  units: { name: string; concepts: string[] }[];
  job: Job | null;
}

/** One section of the notes: its heading path, its transcription and the page it starts on. */
export interface NotesSection {
  location: string;
  text: string;
  page?: number | null;
}

/**
 * One document of the notes as the reader shows it: its sections, in reading order, and how
 * many pages the document itself has when the server can draw them (`original`).
 */
export interface NotesDocument {
  document: string;
  original?: { pages?: number; version?: string; ratios?: number[] } | null;
  sections: NotesSection[];
}

export interface AdminConversationRow extends Omit<ConversationRow, "pending"> {
  author: { id: number; name: string | null; username: string | null };
}

export interface AdminConversationListing {
  workspace: string;
  conversations: AdminConversationRow[];
  total: number;
  limit: number;
  offset: number;
  authors: AdminConversationRow["author"][];
}

export interface AdminConversation extends Omit<ConversationRow, "turns" | "pending"> {
  author: AdminConversationRow["author"];
  turns: (Turn & { decided_by?: string; checks?: unknown; prompt?: string })[];
}
