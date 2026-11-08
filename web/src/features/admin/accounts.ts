import type { AdminAccount, AdminEngines, EngineUse } from "@/lib/types";
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

/**
 * The accounts that are in a subject now, by id: every membership of it a teacher has not
 * paused, whatever its role. What «Permisos de uso» ticks at once for a whole class.
 */
export function accountsIn(accounts: Pick<AdminAccount, "id" | "workspaces">[], slug: string): number[] {
  return accounts.filter((account) => isIn(account, slug)).map((account) => account.id);
}

/**
 * The chosen subjects each account is in now, by id, in the order given: who uses a function
 * through «Asignaturas elegidas», and through which. The same reading as `accountsIn`, so the
 * subjects' list and the accounts' shortcut agree on who is in a class. An account in none of
 * them has no entry.
 */
export function coveredBy(
  accounts: Pick<AdminAccount, "id" | "workspaces">[],
  slugs: readonly string[],
): Map<number, string[]> {
  const covered = new Map<number, string[]>();
  for (const account of accounts) {
    const where = slugs.filter((slug) => isIn(account, slug));
    if (where.length > 0) covered.set(account.id, where);
  }
  return covered;
}

/** Whether an account is in a subject now: it has a membership there a teacher has not paused. */
function isIn(account: Pick<AdminAccount, "workspaces">, slug: string): boolean {
  return account.workspaces.some((row) => row.slug === slug && !row.disabled);
}

/** One option of an account's «Motor»: `null` is the installation's default, named by `name`. */
export interface EngineOption {
  value: string | null;
  name: string;
}

/**
 * What an account's «Motor» offers: the default first, then every engine the installation
 * offers, by its own name.
 *
 * The default and the default engine named are two options and not one: the first follows the
 * installation if its default changes, the second keeps the account where it is. An engine the
 * account runs on and the installation no longer offers is listed last, so the select says
 * the truth about the account instead of showing another engine.
 */
export function engineOptions(
  engines: Pick<AdminEngines, "default" | "offered">,
  current: string | null | undefined,
): EngineOption[] {
  const offered = Array.isArray(engines.offered) ? engines.offered : [];
  const names = current && !offered.includes(current) ? [...offered, current] : offered;
  return [{ value: null, name: engines.default }, ...names.map((name) => ({ value: name, name }))];
}

/**
 * What an engine is doing, in a word: «Sin usuarios» when no account runs on it (and so the
 * server holds no instance of it), else whether its instance is live.
 */
export type EngineState = "unused" | "live" | "idle";

export function engineState(engine: Pick<EngineUse, "users" | "live">): EngineState {
  if (!(engine.users > 0)) return "unused";
  return engine.live ? "live" : "idle";
}
