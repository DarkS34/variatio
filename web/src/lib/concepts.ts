import type { KgConcept } from "@/lib/types";

/**
 * Same rules `VariantGenerator._select_few_shot` applies: any tag counts, not just the
 * primary, and the modality is a HARD filter — an exemplar of another modality is never
 * shown to the model, so with `itemType` given it must not be counted here either.
 *
 * `itemType` is null when the profile declares a single modality: there every item is of
 * it, the untyped ones included, which is exactly what the total already says.
 */
export function exemplarCount(concept: KgConcept, itemType?: string | null): number {
  if (!itemType) return concept.exemplars;
  return concept.exemplars_by_type?.[itemType] ?? 0;
}

export function hasExemplars(concept: KgConcept, itemType?: string | null): boolean {
  return exemplarCount(concept, itemType) > 0;
}
