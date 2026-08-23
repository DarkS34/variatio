import type { GenerationRow } from "@/lib/types";

import { EMPTY_FORM, type FormState } from "./GenerateForm";

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
  };
}
