import { fold } from "@/lib/text";
import type { Key } from "@/lib/i18n";
import type { Member, MemberVia } from "@/lib/types";

/**
 * What the class list decides without React: who is a student, which of them a filter
 * shows, what a search matches, and what an origin is called.
 */

/** The three readings of the students' list. */
export type MemberFilter = "active" | "disabled" | "all";

/** A subject's students — `viewer`s — active and paused, by name. Teachers are listed apart. */
export function studentsOf(members: Member[]): Member[] {
  return members
    .filter((member) => member.role === "viewer")
    .sort((a, b) => a.name.localeCompare(b.name) || a.username.localeCompare(b.username));
}

/** Whether a person is shown under a filter: open access, paused, or either. */
export function inFilter(member: Pick<Member, "disabled_at">, filter: MemberFilter): boolean {
  if (filter === "all") return true;
  return filter === "disabled" ? member.disabled_at !== null : member.disabled_at === null;
}

/** Whether what was typed is part of the person's name or username, accents and case aside. */
export function matchesMember(member: Pick<Member, "name" | "username">, query: string): boolean {
  const wanted = fold(query.trim());
  if (!wanted) return true;
  return [member.name, member.username].some((value) => !!value && fold(value).includes(wanted));
}

const VIA_KEYS: Record<MemberVia, Key> = {
  class_link: "class.via.classLink",
  invite: "class.via.invite",
  admin: "class.via.admin",
  owner: "class.via.owner",
  cli: "class.via.cli",
};

/** The name of how somebody came in, or null when it was never recorded or is unknown here. */
export function viaKey(via: string | null): Key | null {
  return via !== null && via in VIA_KEYS ? VIA_KEYS[via as MemberVia] : null;
}
