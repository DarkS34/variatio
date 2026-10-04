import type { Translate } from "@/lib/i18n";

/**
 * The refusal of the installation's daily limit per account (`tutor.daily_messages`): its
 * code, and its sentence in the reader's language.
 *
 * The server sends a Spanish sentence with the code; the screen builds its own from the code
 * and the `Retry-After` header, and shows the server's only when the header is absent.
 */

/** What the server puts in `X-Error-Code` when the limit is reached. */
export const DAILY_LIMIT = "tutor_daily_limit";

/**
 * How long until the limit reopens, in hours and minutes, never under one minute.
 *
 * The same rounding as the server's own sentence (`tutor/api/usage.py`), so both say the same
 * wait.
 */
export function waitInWords(seconds: number, { t, plural }: Translate): string {
  const total = Math.max(Math.floor(seconds / 60), 1);
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  if (hours === 0) return plural("tutor.limit.minutes", minutes);
  if (minutes === 0) return plural("tutor.limit.hours", hours);
  return t("tutor.limit.both", {
    hours: plural("tutor.limit.hours", hours),
    minutes: plural("tutor.limit.minutes", minutes),
  });
}

/** The sentence of the refusal: when the next message can go, or the server's if it gave no wait. */
export function limitSentence(retryAfter: number | null, fallback: string, tr: Translate): string {
  if (retryAfter === null) return fallback;
  return tr.t("tutor.limit.reached", { wait: waitInWords(retryAfter, tr) });
}
