import { fold } from "@/lib/text";
import type { InviteRow, InviteState, InviteTerms, MintedInvite, Role } from "@/lib/types";

/**
 * What the invitations panel decides without React: the dates its picker writes, the state
 * a row is drawn in, what a search matches and what «Copiar todas» puts on the clipboard.
 */

/** The quick choices beside the date, in calendar days from now. */
export const EXPIRY_PRESETS = [
  { key: "day", days: 1 },
  { key: "week", days: 7 },
  { key: "month", days: 30 },
  { key: "quarter", days: 90 },
] as const;

export type ExpiryPreset = (typeof EXPIRY_PRESETS)[number]["key"];

/** A new invitation's date when nobody touches the picker — the server's own default week. */
export const DEFAULT_EXPIRY_DAYS = 7;

/** How many invitations one request may mint; the server says the same and refuses above it. */
export const BATCH_MAX = 50;

/** The alias column's width, mirrored so the input stops where the server would refuse. */
export const LABEL_MAX = 120;

const pad = (n: number) => String(n).padStart(2, "0");

/** What an `<input type="datetime-local">` holds for this moment, in the reader's own zone. */
export function toLocalInput(date: Date): string {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/**
 * The moment a `datetime-local` value names, or null when it names none.
 *
 * A date-time with no offset is LOCAL time in `Date`'s grammar, which is exactly what the
 * control shows; the ISO string sent from it carries the offset, so the server never has
 * to guess the reader's zone.
 */
export function fromLocalInput(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * `days` calendar days from `now`, to the minute.
 *
 * Calendar days and not multiples of 24 hours: across a change of clock the second would
 * move the wall-clock time the preset is read as by an hour.
 */
export function inDays(days: number, now: Date = new Date()): Date {
  const date = new Date(now);
  date.setDate(date.getDate() + days);
  date.setSeconds(0, 0);
  return date;
}

/** Whether a picker value is a moment still to come — the one thing the server refuses. */
export function isAhead(value: string, now: number = Date.now()): boolean {
  const date = fromLocalInput(value);
  return date !== null && date.getTime() > now;
}

/**
 * The state a row is drawn in: the server's, or — from an API older than the field —
 * read off its date.
 */
export function inviteState(
  row: Pick<InviteRow, "state" | "expires_at">,
  now: number = Date.now(),
): InviteState {
  if (row.state === "pending" || row.state === "expired") return row.state;
  return new Date(row.expires_at).getTime() > now ? "pending" : "expired";
}

/** Whether a row answers a search: its alias, its asignatura or who issued it. */
export function matchesInvite(
  row: Pick<InviteRow, "label" | "workspace" | "workspace_slug" | "created_by">,
  query: string,
): boolean {
  const wanted = fold(query.trim());
  if (!wanted) return true;
  return [row.label, row.workspace, row.workspace_slug, row.created_by].some(
    (value) => !!value && fold(value).includes(wanted),
  );
}

/**
 * A batch as it is copied: one invitation per line, «alias TAB link».
 *
 * The tab is what makes it paste into a spreadsheet as two columns. Either every line
 * carries the alias column or none does, so an unnamed row inside a named batch still
 * lines its link up with the others.
 */
export function linkLines(minted: Pick<MintedInvite, "invite" | "link">[]): string {
  const named = minted.some(({ invite }) => !!invite.label);
  return minted
    .map(({ invite, link }) => (named ? `${invite.label ?? ""}\t${link}` : link))
    .join("\n");
}

/**
 * An invitation's terms as the form holds them: text as typed, and the date as the
 * `datetime-local` control keeps it. `workspace` is a slug, and "" is «ninguna».
 */
export interface TermsDraft {
  label: string;
  workspace: string;
  role: Role;
  expires: string;
}

/** The form for a new invitation: no alias, the first asignatura, the default week. */
export function newDraft(firstWorkspace: string | undefined, now: Date = new Date()): TermsDraft {
  return {
    label: "",
    workspace: firstWorkspace ?? "",
    role: "editor",
    expires: toLocalInput(inDays(DEFAULT_EXPIRY_DAYS, now)),
  };
}

/** The form for an existing invitation, holding exactly what it has now. */
export function draftOf(row: Pick<InviteRow, "label" | "workspace_slug" | "role" | "expires_at">): TermsDraft {
  return {
    label: row.label ?? "",
    workspace: row.workspace_slug ?? "",
    role: row.role,
    expires: toLocalInput(new Date(row.expires_at)),
  };
}

/** What a new invitation is asked for with; null while the date names no moment. */
export function termsOf(draft: TermsDraft): InviteTerms | null {
  const expires = fromLocalInput(draft.expires);
  if (!expires) return null;
  return {
    workspace: draft.workspace || null,
    role: draft.role,
    expires_at: expires.toISOString(),
    label: draft.label.trim() || null,
  };
}

/**
 * Only what an edit actually changes, so an expired invitation can be renamed without
 * being made to move its date — the one term the server would refuse as it stands.
 *
 * The date is compared as the control shows it, to the minute: an untouched picker never
 * reads as a change because the stored moment carried seconds.
 */
export function changesOf(
  row: Pick<InviteRow, "label" | "workspace_slug" | "role" | "expires_at">,
  draft: TermsDraft,
): Partial<InviteTerms> {
  const before = draftOf(row);
  const changes: Partial<InviteTerms> = {};
  if (draft.label.trim() !== before.label) changes.label = draft.label.trim() || null;
  if (draft.workspace !== before.workspace) changes.workspace = draft.workspace || null;
  if (draft.role !== before.role) changes.role = draft.role;
  if (draft.expires !== before.expires) {
    const expires = fromLocalInput(draft.expires);
    if (expires) changes.expires_at = expires.toISOString();
  }
  return changes;
}
