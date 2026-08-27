import type { EvaluatorProfile } from "@/lib/types";

/**
 * The two evaluator profiles, named once for the whole browser.
 *
 * What each one is ASKED is deliberately not here: the wording is the instrument, it lives
 * in `study/api/instruments.py` and it arrives with the listing. These are labels for the
 * screens that SET the profile, which is a property of the account — the same reason the
 * Python keeps `EVALUATOR_PROFILES` in `server/db/models.py` and not in `study/`.
 */
export const PROFILES: EvaluatorProfile[] = ["teacher", "student"];

export const PROFILE_LABELS: Record<EvaluatorProfile, string> = {
  teacher: "Docente",
  student: "Alumno",
};

/**
 * The same two, said in the first person, for the one screen where somebody classifies
 * THEMSELVES. Verbs and not nouns because a noun has to pick a gender — «alumno» — and the
 * installation does not know one; «¿das clase o estudias?» asks the same thing of anybody.
 */
export const PROFILE_SELF_LABELS: Record<EvaluatorProfile, string> = {
  teacher: "Docente",
  student: "Estudiante",
};

/** `null` is a state and not a gap, so it is named rather than left blank. */
export function profileLabel(value: EvaluatorProfile | null | undefined): string {
  return value ? PROFILE_LABELS[value] : "Sin perfil";
}
