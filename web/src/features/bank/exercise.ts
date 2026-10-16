import { EMPTY_FORM, type FormState } from "@/consumers/generation/commission";
import { fieldToInput, inputToField } from "@/lib/fields";
import { difficultyFieldOf, difficultyLevelsOf } from "@/lib/profile";
import type { BankItemType, ExemplarsProfile, ItemTypeSpec, ReadableExercise } from "@/lib/types";

/*
 * How «Nuevo ejercicio» reads a type's fields and writes what was typed into them, as the
 * bank's schema takes it (`ExemplarsProfile._spec_to_field`): every field is required unless
 * it has a default or allows null, and one that allows null must still be sent, as null.
 */

/** The fields of a type in the order the profile declares them, the statement first. */
export function orderedFields(summary: BankItemType | undefined, spec: ItemTypeSpec | null): string[] {
  const declared = spec ? Object.keys(spec.fields) : (summary?.fields ?? []);
  const primary = spec?.primary_field ?? summary?.primary_field;
  return primary && declared.includes(primary)
    ? [primary, ...declared.filter((name) => name !== primary)]
    : declared;
}

/** Whether the bank refuses an exercise without this field: no default and no null allowed. */
export function isRequired(schema: Record<string, any>): boolean {
  if ("default" in schema) return false;
  const types = Array.isArray(schema.type) ? schema.type : [schema.type];
  return !types.includes("null");
}

/** Whether a field holds a list, written one entry per line. */
export function isList(schema: Record<string, any>): boolean {
  const types = Array.isArray(schema.type) ? schema.type : [schema.type];
  return types.includes("array");
}

/** What a field's text is stored as: a list, a number, an object, or the text itself. */
export function valueOf(raw: string, schema: Record<string, any>): unknown {
  const types: unknown[] = Array.isArray(schema.type) ? schema.type : [schema.type];
  if (types.includes("array")) return inputToField(raw, true);
  if (types.includes("object")) {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : undefined;
    } catch {
      return undefined;
    }
  }
  if ((types.includes("integer") || types.includes("number")) && !types.includes("string")) {
    const number = Number(raw);
    return Number.isFinite(number) ? number : raw;
  }
  return raw;
}

/** The fields of an exercise already written, as the form edits them. */
export function inputsOf(fields: Record<string, unknown> | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [name, value] of Object.entries(fields ?? {})) {
    out[name] =
      value && typeof value === "object" && !Array.isArray(value)
        ? JSON.stringify(value, null, 2)
        : fieldToInput(value);
  }
  return out;
}

/**
 * The types of a profile as the bank's listing describes them, for a screen that has the
 * profile and no listing — «Generar ejercicios» passing one of its exercises into the bank.
 */
export function typeSummaries(profile: ExemplarsProfile | null): BankItemType[] {
  return Object.entries(profile?.item_types ?? {}).map(([key, spec]) => ({
    key,
    label: spec.label || key,
    description: spec.description ?? "",
    primary_field: spec.primary_field,
    embed_fields: spec.embed_fields ?? [spec.primary_field],
    fields: Object.keys(spec.fields),
    difficulty_field: difficultyFieldOf(spec),
    difficulty_levels: difficultyLevelsOf(spec),
    count: 0,
  }));
}

/**
 * A commission like one exercise of the bank a student reads: its type, its level and its
 * concepts, the one it is about first. The rest of the form starts as a new one.
 */
export function commissionLike(item: ReadableExercise, type: BankItemType | null): FormState {
  const field = type?.difficulty_field ?? null;
  const level = field ? item[field] : undefined;
  const primary = item.primary_concept;
  return {
    ...EMPTY_FORM,
    concepts: [...new Set([...(primary ? [primary] : []), ...item.concepts])],
    itemType: item.item_type || null,
    decisions: field && typeof level === "string" && level ? { [field]: level } : {},
  };
}
