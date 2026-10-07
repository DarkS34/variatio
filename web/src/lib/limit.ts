import type { Translate } from "@/lib/i18n";

/**
 * The refusals of a limit per account and day — a student's exercises here, the tutor's
 * messages in its folder — said in the reader's language.
 *
 * The server sends a Spanish sentence with the code; a screen builds its own from the code and
 * the `Retry-After` header, and shows the server's only when the header is absent.
 */

/** What the server puts in `X-Error-Code` when a student's exercises of the day are spent. */
export const GENERATION_DAILY_LIMIT = "generation_daily_limit";

/**
 * How long until a limit reopens, in hours and minutes, never under one minute.
 *
 * The same rounding as the server's own sentence (`server/daily.py`), so both say the same
 * wait.
 */
export function waitInWords(seconds: number, { t, plural }: Translate): string {
  const total = Math.max(Math.floor(seconds / 60), 1);
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  if (hours === 0) return plural("limit.minutes", minutes);
  if (minutes === 0) return plural("limit.hours", hours);
  return t("limit.both", {
    hours: plural("limit.hours", hours),
    minutes: plural("limit.minutes", minutes),
  });
}

/**
 * What a refused commission says: the day's limit in the reader's words when that is the
 * refusal and the wait came with it, the server's sentence otherwise.
 */
export function launchError(
  error: { message: string; code?: string | null; retryAfter?: number | null },
  tr: Translate,
): string {
  if (error.code !== GENERATION_DAILY_LIMIT || error.retryAfter == null) return error.message;
  return tr.t("limit.generation.reached", { wait: waitInWords(error.retryAfter, tr) });
}

/** What a student may still ask for today, or null when the day has no limit. */
export function leftToday(allowance: { daily_items: number | null; used_today: number }): number | null {
  if (allowance.daily_items === null) return null;
  return Math.max(0, allowance.daily_items - allowance.used_today);
}
