import type { GenerationRow } from "@/lib/types";

import { EMPTY_FORM, type FormState } from "./commission";

const KEY = "vg.generate.draft";

export function stashDraft(form: FormState): void {
  sessionStorage.setItem(KEY, JSON.stringify(form));
}

export function takeDraft(): FormState | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  sessionStorage.removeItem(KEY);
  try {
    return { ...EMPTY_FORM, ...(JSON.parse(raw) as Partial<FormState>) };
  } catch {
    return null;
  }
}

export function fromGeneration(row: GenerationRow): FormState {
  return {
    ...EMPTY_FORM,
    concepts: [...row.concepts],
    itemType: row.item_type || null,
    useCurriculum: row.curriculum.length > 0,
    usePresetCurriculum: false,
    curriculum: [...row.curriculum],
    decisions: { ...row.fixed },
    instructions: row.instructions ?? "",
    think: row.think,
    // The model is deliberately NOT carried over, even though the row records one: nobody
    // chooses a writer any more, so a re-run goes out with none and the installation
    // resolves its own. Carrying it would send a name the form cannot show and the person
    // cannot change.
  };
}
