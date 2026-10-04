/**
 * A conversation to open on arrival, handed over from another screen.
 *
 * «Trabajar con el tutor» on a generated exercise lands here with the statement already in the
 * box and the exercise named, so the tutor starts on that exercise's concepts. Kept in the
 * session's storage and taken once, as the generation form's draft is: a reload does not
 * open it a second time.
 *
 * In core and not in `tutor/`, because the screens that stash it are core and import
 * nothing of the tutor; they offer the button only when the tutor is open to the account.
 */
const KEY = "vg.tutor.draft";

export interface TutorDraft {
  message: string;
  generationId: string | null;
}

export function stashTutorDraft(draft: TutorDraft): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(draft));
  } catch {
    /* without storage the tutor simply opens empty */
  }
}

export function takeTutorDraft(): TutorDraft | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    const parsed = JSON.parse(raw) as Partial<TutorDraft>;
    return typeof parsed.message === "string"
      ? { message: parsed.message, generationId: parsed.generationId ?? null }
      : null;
  } catch {
    return null;
  }
}
