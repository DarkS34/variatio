/** The generated exercises: a commission's parameters and bounds, and what it produced. */

export interface GenerateParams {
  n: number;
  concepts: string[];
  item_type?: string;
  fixed?: Record<string, unknown>;
  /** The fields this commission leaves out, among the ones the profile marks `omittable`. */
  omit?: string[];
  curriculum?: string[];
  instructions?: string;
  /** Whether the model deliberates before writing: `false` is off, a string names the
   *  effort level, and absent means yes at the default level, as it always did. */
  think?: boolean | string;
  /** Which of the offered models writes it; absent is the first one the installation
   *  offers, which is what the server resolves and what the row then records. */
  model?: string;
}

/** One exemplar exactly as it went into the few-shot block of the prompt. */
export interface FewShotExemplar {
  id: string;
  item: Record<string, unknown>;
  /** `neighbour` is an exemplar of a direct prerequisite, shown as form and not as objective. */
  origin?: "primary" | "secondary" | "neighbour";
}

/** What this account may ask for in one commission and in the day, here. */
export interface Allowance {
  max_items: number;
  /** Null without a daily limit, which is always a teacher's case. */
  daily_items: number | null;
  /** Exercises asked for today, across every subject; counted only under a limit. */
  used_today: number;
}

export interface GenerationAuthor {
  id: number | null;
  name: string | null;
  username: string | null;
}

export interface ItemChecks {
  forbidden: string[];
  similarity: { to: string; score: number; high: boolean } | null;
  tagger?: {
    primary: string | null;
    concepts: string[];
    method: string | null;
    on_target: boolean;
    targets_found: string[];
  };
  flags: string[];
  /** The two hard signals alone (a forbidden mention, a near copy) ask for a retry. */
  verdict?: "accept" | "retry";
  reasons?: string[];
}

export interface GenerationRow {
  /** The name of its file. A number from an API that still kept them in a table. */
  id: string;
  created_at: number;
  job_id: string | null;
  item_type: string;
  /** What was ASKED for, which is what «Generar más como este» reopens. */
  concepts: string[];
  /** What ran: the bank's most frequent concepts when nothing was asked. Absent from an
   *  older API. */
  targets?: string[];
  curriculum: string[];
  fixed: Record<string, unknown>;
  /** The parts the commission left out; absent on an exercise saved before it could. */
  omit?: string[];
  instructions: string;
  /** As asked: off, on, or the level it was asked at. */
  think: boolean | string;
  /** The effort that ran, once an installation's lock is applied; null when unrecorded. */
  effort?: boolean | string | null;
  /** The model that WROTE it. Null for every row from before the commission could choose,
   *  where naming today's default would be inventing a fact. */
  model: string | null;
  author: GenerationAuthor;
  promoted_item_id: string | null;
  /** The bank's id while the exercise passed into it is still there: a teacher's reading.
   *  Absent on an older API, which said only `promoted_item_id`. */
  in_bank?: string | null;
  /** Whether this account may pass it into the bank: a teacher's own, not in it. Absent on
   *  an older API (the demo's), where «Pasar al banco» is not drawn. */
  promotable?: boolean;
  item: Record<string, unknown>;
  checks?: ItemChecks | null;
}

/** How a generated exercise goes into the bank (`POST /api/generations/{id}/promote`). */
export interface PromoteBody {
  fields?: Record<string, unknown>;
  tag: "auto" | "manual";
  concepts?: string[];
  primary_concept?: string | null;
  visibility?: { level: "hidden" | "full" | "fields"; fields: string[]; groups?: number[] | null };
}

export interface GenerationListing {
  generations: GenerationRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface GenerationDetail {
  generation: GenerationRow & {
    thinking: string | null;
    retried?: number | null;
    /** 1 for an exercise saved as a file, 0 for one exported from the retired table. */
    format?: number;
    /** How it was made, beyond what was asked: null wherever it was never recorded. */
    provenance?: {
      resolved: Record<string, unknown> | null;
      inputs: Record<string, string | null> | null;
      settings: Record<string, unknown> | null;
      system_version: string | null;
      prompt: string | null;
    };
  };
}
