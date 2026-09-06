import type { EvaluatorProfile } from "@/lib/types";
import type { Key } from "@/lib/i18n";

/**
 * The two evaluator profiles, named once for the whole browser.
 *
 * What each one is ASKED is deliberately not here: the wording is the instrument, it lives
 * in `evaluation/api/instruments.py` and it arrives with the listing. These are labels for the
 * screens that SET the profile, which is a property of the account — the same reason the
 * Python keeps `EVALUATOR_PROFILES` in `server/db/models.py` and not in `evaluation/`.
 */
export const PROFILES: EvaluatorProfile[] = ["teacher", "student"];

export const PROFILE_LABEL_KEYS: Record<EvaluatorProfile, Key> = {
  teacher: "profile.teacher",
  student: "profile.student",
};

/**
 * The same two, said in the first person, for the one screen where somebody classifies
 * THEMSELVES. Verbs and not nouns because a noun has to pick a gender — "alumno" — and the
 * installation does not know one; "¿das clase o estudias?" asks the same thing of anybody.
 */
export const PROFILE_SELF_LABEL_KEYS: Record<EvaluatorProfile, Key> = {
  teacher: "profile.self.teacher",
  student: "profile.self.student",
};

/** `null` is a state and not a gap, so it is named rather than left blank. */
export function profileLabel(
  value: EvaluatorProfile | null | undefined,
  t: (key: Key) => string,
): string {
  return value ? t(PROFILE_LABEL_KEYS[value]) : t("evaluator.noProfile");
}
