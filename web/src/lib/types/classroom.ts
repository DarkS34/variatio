/** «Clase»: the people of a subject, its groups, links and invitations, and the activity. */

import type { InviteState } from "./admin";
import type { Role } from "./auth";

/** A student of the subject, as the activity names them; `disabled` when a teacher paused them. */
export interface ActivityStudent {
  id: number;
  name: string;
  username: string;
  disabled: boolean;
}

/** One week of the strip: its two figures and whether its digest is written. */
export interface ActivityWeekSummary {
  week: string;
  /** Its Monday, `YYYY-MM-DD`. */
  start: string;
  messages: number;
  exercises: number;
  /** Messages to the free chat; absent on an API without it. */
  chat?: number;
  active: number;
  digest: boolean;
}

/** `GET /api/activity/weeks`: the class's weeks, the newest first, and who is in the class. */
export interface ActivityHistory {
  current: string;
  weeks: ActivityWeekSummary[];
  students: ActivityStudent[];
  /** Whether the tutor is installed: without it there is nothing of the tutor to count. */
  tutor: boolean;
  /** Whether the free chat is installed; absent on an older API, which has none. */
  chat?: boolean;
}

/** The page of «Actividad» a finding belongs to; an older API sends none. */
export type ActivityArea = "tutor" | "exercises" | "chat";

/** What a teacher should read first about a week, typed: the screen words it. */
export type ActivityFinding = { area?: ActivityArea } & (
  | { kind: "asked"; concept: string; students: number; of: number; prerequisite: string | null; sent_back: number }
  | { kind: "solutions"; concept: string; solution: number; messages: number }
  | { kind: "unpractised"; units: string[]; more: number }
  | { kind: "idle"; students: number; of: number; open: boolean }
  | { kind: "trend"; active: number; previous: number; open: boolean }
  | { kind: "quiet"; open: boolean }
  | { kind: "topic"; concept: string; messages: number }
  | { kind: "reviewed"; prerequisite: string; times: number }
  | { kind: "practised"; unit: string; exercises: number }
);

export interface ActivityTutor {
  messages: number;
  students: number;
  /** By the kind of reply each message got (`theory`, `solution`…). */
  by_kind: Record<string, number>;
  by_concept: { concept: string; unit: string | null; messages: number; students: number }[];
  sent_back: { concept: string; prerequisite: string; times: number; students: number }[];
  /** Monday first. */
  per_day: number[];
}

export interface ActivityExercises {
  count: number;
  students: number;
  by_type: { type: string; count: number; levels: Record<string, number> }[];
  by_concept: { concept: string; unit: string | null; count: number; students: number }[];
  /** Every unit of the syllabus in order; `covered` only where the course's progress is set. */
  by_unit: { unit: string; count: number; covered: boolean | null }[];
  to_tutor: number;
  per_day: number[];
}

export interface ActivityDigestTheme {
  text: string;
  messages: number;
  students: number;
  /** In one student's reading: how many of the theme's messages are theirs. */
  mine?: number;
}

export interface ActivityDigest {
  written_at: string | null;
  messages_seen: number;
  /** Messages about the subject sent after it was written. */
  new_since: number;
  concepts: { concept: string; unit: string | null; themes: ActivityDigestTheme[] }[];
}

export interface ActivityStudentRow extends ActivityStudent {
  messages: number;
  exercises: number;
  /** Messages to the free chat; absent on an API without it. */
  chat_messages?: number;
  /** Messages and exercises per day, Monday first. */
  days: number[];
  /** The same days, the messages and the exercises apart; an older API sends neither. */
  message_days?: number[];
  exercise_days?: number[];
  chat_days?: number[];
}

/** A week of the free chat: how many messages, from how many students, day by day. */
export interface ActivityChat {
  messages: number;
  students: number;
  per_day: number[];
}

/** `GET /api/activity/weeks/{week}`: one week of the class, or of one student. */
export interface ActivityWeek {
  week: string;
  start: string;
  closed: boolean;
  scope: "class" | "student";
  student: ActivityStudent | null;
  class_size: number;
  tutor: ActivityTutor | null;
  exercises: ActivityExercises;
  /** Null where the chat is not installed; absent on an older API. */
  chat?: ActivityChat | null;
  digest: ActivityDigest | null;
  digest_ready: boolean;
  digest_running?: boolean;
  tutor_offered?: boolean;
  findings: ActivityFinding[];
  /** The class's reading only. */
  students?: ActivityStudentRow[];
  /** One student's reading only: the class's median, the idle included. */
  median?: { messages: number; exercises: number; chat?: number };
}

/** What a subject's teachers let its students use (`GET /api/members/uses`). */
/** A tool a group of the class has open (true), closed (false), or as the subject (null). */
export type GroupTool = boolean | null;

export interface StudentUses {
  generate: boolean;
  tutor: boolean;
  /** The free chat's switch, once the chat exists (`chat`); absent before it. */
  chat?: boolean;
  /** Read for one group (`?group=`): its own three values beside the subject's. */
  group?: { id: number; name: string; generate: GroupTool; tutor: GroupTool; chat: GroupTool };
  /** Whether the tutor is installed: without it there is no switch of it to draw. An older
   *  API sends none, and then the switch is drawn only where the tutor is offered. */
  tutor_installed?: boolean;
  /** Whether the administrator opened the tutor to anybody studying here: without it the
   *  subject's own switch for the tutor is drawn switched off, and says why. */
  tutor_offered: boolean;
}

/** How somebody entered a subject; null when it was never recorded. */
export type MemberVia = "owner" | "admin" | "invite" | "class_link" | "cli";

/** One person of a subject, as its teachers read the class list: who, as what, since when, how. */
export interface Member {
  user_id: number;
  name: string;
  username: string;
  role: Role;
  joined_at: string | null;
  via: MemberVia | null;
  invited_by: string | null;
  /** When a teacher paused their access; null while it is open. */
  disabled_at: string | null;
  /** The group of the class they are in; absent on an older API. */
  group?: { id: number; name: string } | null;
}

/** A group of the class: its name, its active students, and what it uses (null = as the subject). */
export interface ClassGroup {
  id: number;
  name: string;
  students: number;
  generate: GroupTool;
  tutor: GroupTool;
  chat: GroupTool;
}

/** One gesture over several people; `group` puts them in a group or takes them out. */
export type MemberAction = "disable" | "enable" | "remove" | "group";

/** What a gesture over several people did, and what it refused and why. */
export interface MembersBulkResult {
  done: number[];
  refused: { user_id: number; code: string; reason: string }[];
}

/** A subject's live class link as its teachers read it: how full, until when — never the link. */
export interface ClassLinkView {
  id: number;
  uses: number;
  max_uses: number;
  expires_at: string;
  expired: boolean;
  paused: boolean;
  created_at: string | null;
  created_by: string | null;
  /** Whether its link can be read again; false only when the sealing key was missing. */
  link_stored: boolean;
  /** The group it brings into; null for the class as a whole. */
  group_id?: number | null;
}

/** A class link just minted or renewed: its terms and the link itself. */
export interface MintedClassLink {
  class_link: ClassLinkView;
  link: string;
  stored: boolean;
}

/** New terms for a class link; only the fields sent change. */
export interface ClassLinkTerms {
  max_uses?: number;
  expires_at?: string;
  paused?: boolean;
}

/** One of the subject's personal invitations nobody has used, as its teachers read it. */
export interface MemberInvite {
  id: number;
  label: string | null;
  role: Role;
  profile?: unknown;
  created_at: string | null;
  expires_at: string;
  created_by: string | null;
  state?: InviteState;
  link_stored?: boolean;
  /** The group it brings into, if any. */
  group_id?: number | null;
}

/** A personal invitation a teacher has just minted: its row and the link that IS it. */
export interface MintedMemberInvite {
  invite: MemberInvite;
  link: string;
  stored?: boolean;
  /** Only where it went with an address: whether the mail left. The address is kept nowhere. */
  sent?: boolean;
}
