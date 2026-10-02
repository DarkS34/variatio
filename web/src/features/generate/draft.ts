import type { GenerationRow } from "@/lib/types";

import { EMPTY_FORM, type FormState } from "./commission";
import { EFFORT_ORDER, type EffortLevel } from "./effort";

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
    usePresetCurriculum: false,
    curriculum: [...row.curriculum],
    decisions: { ...row.fixed },
    instructions: row.instructions ?? "",
    // The level it was asked at, which a row before the files could not keep: it said only
    // whether the model reasoned, and that still reopens at the default level.
    think: row.think !== false,
    effort:
      typeof row.think === "string" && EFFORT_ORDER.includes(row.think as EffortLevel)
        ? (row.think as EffortLevel)
        : EMPTY_FORM.effort,
    // "Another like this one" means the same commission, and the model is part of it. A row
    // before it was recorded carries null, which is the default — the same thing that
    // commission ran with.
    model: row.model,
  };
}
