import type { EvaluatorProfile } from "@/lib/types";
import type { Key } from "@/lib/i18n";

/**
 * The account's two profiles, named once for the whole browser: a teacher creates subjects,
 * a student does not, and the invitation decides which an account is.
 *
 * What the evaluation ASKS each one is deliberately not here: the wording is the instrument,
 * it lives in `evaluation/api/instruments.py` and it arrives with the listing. These are
 * labels for the screens that show or set the profile, which is a property of the account —
 * the same reason the Python keeps `EVALUATOR_PROFILES` in `server/db/models.py`.
 */
export const PROFILES: EvaluatorProfile[] = ["teacher", "student"];

export const PROFILE_LABEL_KEYS: Record<EvaluatorProfile, Key> = {
  teacher: "profile.teacher",
  student: "profile.student",
};

/** `null` is a state and not a gap, so it is named rather than left blank. */
export function profileLabel(
  value: EvaluatorProfile | null | undefined,
  t: (key: Key) => string,
): string {
  return value ? t(PROFILE_LABEL_KEYS[value]) : t("evaluator.noProfile");
}
