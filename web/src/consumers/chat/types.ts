import type { Job, JobStatus } from "@/lib/types";

/** One of the account's conversations with the free chat, as the list shows it. */
export interface ChatRow {
  id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
  turns: number;
  pending: boolean;
}

/** Why a message got no reply: its job failed, was stopped, or was lost to a restart. */
export type FailedReason = "failed" | "cancelled" | "interrupted" | string;

export interface ChatStudentTurn {
  role: "student";
  text: string;
  at: string;
  failed?: FailedReason;
}

export interface ChatReplyTurn {
  role: "assistant";
  text: string;
  at: string;
  /** `reply`, or `blocked` when the guardrail answered with its fixed text. */
  kind?: string;
  truncated?: boolean;
}

export type ChatTurn = ChatStudentTurn | ChatReplyTurn;

export interface ChatPending {
  job_id: string;
  turn: number;
  status: JobStatus | null;
  queue_position: number;
  job: Job | null;
}

/** What a conversation was opened on: nothing, or an exercise as the student reads it. */
export type ChatOpenedFrom =
  | { kind: "message" }
  | { kind: "generation" | "bank"; exercise?: [string, string][] };

export interface ChatConversation extends Omit<ChatRow, "turns" | "pending"> {
  opened_from: ChatOpenedFrom;
  turns: ChatTurn[];
  pending: ChatPending | null;
}

/** The conversation, as the routes that change it answer: the record and the job now queued. */
export interface ChatQueued {
  conversation: ChatConversation;
  job: Job;
}
