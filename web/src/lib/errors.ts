import { ApiError } from "./api";
import type { Translate } from "./i18n";

/**
 * What to put on screen when a read failed.
 *
 * An `ApiError` already carries the sentence the API wrote, in the reader's language and
 * about the actual problem — that one goes through untouched. Anything else is the browser
 * talking: `fetch` rejects with `TypeError: Failed to fetch` when the request never left,
 * and that string was reaching people verbatim, in English, under a Spanish heading.
 */
export function errorText(error: unknown, t: Translate["t"]): string {
  if (error instanceof ApiError) return error.message;
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (!message || /failed to fetch|networkerror|load failed|network request failed/i.test(message))
    return t("error.unreachable");
  return message;
}
