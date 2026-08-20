import type { KgConcept } from "@/lib/types";

/** Same rule `ContentGenerator._select_few_shot` applies: any tag counts, not just the primary. */
export function hasExemplars(concept: KgConcept): boolean {
  return concept.exemplars > 0;
}
