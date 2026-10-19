/** Identity: the session, the account, its roles, the optional functions and an invitation. */

import type { AdminFeaturesPayload } from "./admin";

export type Role = "viewer" | "editor" | "owner";

export interface CurrentUser {
  id: number;
  /** What you type to enter, and how you are named everywhere in the app. */
  username: string;
  /** Optional: a delivery address for a link, never an identity. */
  email: string | null;
  name: string;
  is_admin: boolean;
  /**
   * The account's profile: a teacher creates subjects, a student does not (`useCanCreate`).
   * Its invitation set it. Null on an old row, and read as a student's.
   */
  evaluator_profile?: EvaluatorProfile | null;
  /** What the interface is drawn in. Not a workspace's `prompt_language`: see `lib/i18n`. */
  ui_language: string;
}

export interface WorkspaceMembership {
  slug: string;
  name: string;
  role: Role;
  active: boolean;
}

/** A live login of this account: what the profile screen lists so you can spot one you
 *  do not recognise. Never another account's — this is only ever your own. */
export interface Session {
  user: CurrentUser;
  workspaces: WorkspaceMembership[];
  /** Where this account lands when a tab has no preference of its own. */
  active_workspace: string | null;
  /** Role in that workspace; null when the account is a member of nothing at all. */
  role: Role | null;
  /** Whether this INSTALLATION has SMTP: an installation fact, not a property of the
   *  account. False means the reset link is only ever logged and handed back in the
   *  response, so nothing can be delivered to an address. */
  mail_configured: boolean;
  /** What is open to this account where it is: generating and the optional functions.
   *  Absent from an API older than the bundle, so it is never read directly: `featuresOf`
   *  is the one reader. */
  features?: Partial<Openings>;
}

/** The two optional functions (`server/auth/features.py`), as the session reports them. */
export interface Features {
  evaluation: boolean;
  tutor: boolean;
}

/**
 * What is open to the account where it is: the two functions, and generating — open to every
 * account until the administrator narrows it, and a subject's teachers may close it to its
 * students («Clase → Funcionalidades permitidas»). Not an optional function: it has no tone.
 */
export interface Openings extends Features {
  generate: boolean;
  /**
   * The free chat (2026-10-15): a subject's teachers open it to their students, and it starts
   * closed; its teachers always have it. An API that does not send it has no chat.
   */
  chat: boolean;
  /**
   * The class page of the subject in use («Mi clase», `/class`), still its teachers' alone.
   * No server sends it: only the landing's demo closes it (`false`), since its sample
   * subject has nobody to show (the user's request, 2026-10-13).
   */
  class: boolean;
}

/**
 * The account's functions, read defensively.
 *
 * Anything but a literal `true` is closed: an API that does not send the field, or sends it
 * malformed, degrades to the product without the two functions rather than to a bar drawing
 * doors that answer 403 — and so does the chat. Generating is the other way round: only a
 * literal `false` closes it, because an older API never sends it and generating was always
 * open.
 */
export function featuresOf(session: Pick<Session, "features"> | null | undefined): Openings {
  const raw: unknown = session?.features;
  const value = (name: keyof Openings) =>
    typeof raw === "object" && raw !== null ? (raw as Record<string, unknown>)[name] : undefined;
  return {
    evaluation: value("evaluation") === true,
    tutor: value("tutor") === true,
    generate: value("generate") !== false,
    chat: value("chat") === true,
    class: value("class") !== false,
  };
}

/** One optional function, by the name the server keys it with. */
export type FeatureName = keyof Features;

/**
 * A function whose users the administrator chooses (`server/auth/features.GATED`): the two
 * optional ones, and generating and the free chat since 2026-10-19.
 */
export type GatedName = FeatureName | "generate" | "chat";

/** The two functions, in the order of their doors. */
export const FEATURE_NAMES: readonly FeatureName[] = ["evaluation", "tutor"];

/** Who a function is for: nobody, every account, or the accounts on its list. */
export type FeatureMode = "off" | "all" | "selected";

const FEATURE_MODES: readonly FeatureMode[] = ["off", "all", "selected"];

/** One function as the administrator sets it. The list is kept whatever the mode. */
export interface FeatureAccessState {
  mode: FeatureMode;
  /** Account ids, in id order. */
  accounts: number[];
  /** Subject slugs, in slug order: everybody in one uses the function there. The tutor's
   *  alone (`server/auth/features.SUBJECT_LISTED`); absent for the evaluation and an older API. */
  workspaces?: string[];
}

/** The functions a whole subject may be listed for, as the server declares them. */
export const SUBJECT_LISTED: readonly GatedName[] = ["generate", "tutor", "chat"];

/** The functions a subject's teachers also open or close to its students («Clase»). */
export const SUBJECT_SWITCHED: readonly GatedName[] = ["generate", "tutor", "chat"];

/** The mode of a function nobody has set: the optional ones start off, the product's own open. */
const DEFAULT_MODE: Record<GatedName, FeatureMode> = {
  generate: "all",
  evaluation: "off",
  tutor: "off",
  chat: "all",
};

/**
 * One function's mode and list, read defensively.
 *
 * Anything unreadable is the server's own default — off for an optional function, open for
 * generating and the chat, with an empty list — so an older API, or a malformed answer, draws
 * the function as the server would rather than blanking the tab.
 */
export function featureAccessOf(
  payload: AdminFeaturesPayload | null | undefined,
  feature: GatedName,
): FeatureAccessState {
  const raw: unknown = payload?.features?.[feature];
  const record = typeof raw === "object" && raw !== null ? (raw as Record<string, unknown>) : {};
  const mode = FEATURE_MODES.find((known) => known === record.mode) ?? DEFAULT_MODE[feature];
  const accounts = Array.isArray(record.accounts)
    ? record.accounts.filter((id): id is number => Number.isInteger(id))
    : [];
  if (!SUBJECT_LISTED.includes(feature)) return { mode, accounts };
  const workspaces = Array.isArray(record.workspaces)
    ? record.workspaces.filter((slug): slug is string => typeof slug === "string")
    : [];
  return { mode, accounts, workspaces };
}

/**
 * The account's profile: a teacher's or a student's. The invitation that created the account
 * set it, and only the administrator raises it; nothing lowers it. It decides one thing,
 * creating subjects, and authorises nothing inside one — that is the membership's role.
 * `null` survives only on an API older than the profile, and reads as a student's.
 */
export type EvaluatorProfile = "teacher" | "student";

/** The two kinds of link one address carries: one person's invitation, or a class's link. */
export type InviteKind = "personal" | "class";

export interface InvitePreview {
  /** Absent from an API older than class links, whose every link was a personal one. */
  kind?: InviteKind;
  role: Role;
  workspace: string | null;
  expires_at: string;
  /**
   * What the account will be: the invitation says it and the form never asks. Absent from
   * an API older than the account's profile.
   */
  profile?: EvaluatorProfile;
  /** Who invites, by the name they show; null when that account is gone. */
  inviter?: string | null;
  /** A class link its teacher paused: it lets nobody in until it is resumed. */
  paused?: boolean;
}

/** What joining with an account that already exists answers: the session, and whether it was in. */
export type JoinedSession = Session & { already: boolean };
