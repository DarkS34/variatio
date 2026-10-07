import type { Translate } from "@/lib/i18n";
import { waitInWords } from "@/lib/limit";

/**
 * The refusal of the installation's daily limit per account (`tutor.daily_messages`): its
 * code, and its sentence in the reader's language.
 *
 * The server sends a Spanish sentence with the code; the screen builds its own from the code
 * and the `Retry-After` header, and shows the server's only when the header is absent.
 */

/** What the server puts in `X-Error-Code` when the limit is reached. */
export const DAILY_LIMIT = "tutor_daily_limit";

/** The sentence of the refusal: when the next message can go, or the server's if it gave no wait. */
export function limitSentence(retryAfter: number | null, fallback: string, tr: Translate): string {
  if (retryAfter === null) return fallback;
  return tr.t("tutor.limit.reached", { wait: waitInWords(retryAfter, tr) });
}
