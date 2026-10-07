import type { AdminAccount } from "@/lib/types";
import { fold } from "@/lib/text";

/**
 * THE KINDS OF ACCOUNT: each account is listed under one, by what it most is.
 *
 * A deactivated account is that before anything else, and an administrator before a
 * profile: the first is who cannot enter, the second who enters everywhere. The other
 * accounts are told apart by their profile, which their invitation set. There is no kind
 * for an account with none: migration 0017 left none, and an older API's NULL reads as a
 * student's, as the server reads it.
 */
export type GroupKey = "teachers" | "students" | "admins" | "disabled";

export function groupOf(account: Pick<AdminAccount, "disabled" | "is_admin" | "evaluator_profile">): GroupKey {
  if (account.disabled) return "disabled";
  if (account.is_admin) return "admins";
  if (account.evaluator_profile === "teacher") return "teachers";
  return "students";
}

/** Whether what was typed is part of the account's name or of its username. */
export function matchesAccount(account: Pick<AdminAccount, "name" | "username">, query: string): boolean {
  const wanted = fold(query.trim());
  if (!wanted) return true;
  return [account.name, account.username].some((value) => !!value && fold(value).includes(wanted));
}
