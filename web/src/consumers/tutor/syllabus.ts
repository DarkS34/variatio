import { fold } from "@/lib/text";

/**
 * The subject's syllabus as a student chooses from it: units in order, each with the
 * concepts a conversation can stand on (`GET /api/tutor/syllabus`).
 */
export interface SyllabusUnit {
  name: string;
  concepts: string[];
}

/** What a search found in one unit. `number` is the unit's place in the syllabus, from 1. */
export interface UnitMatch {
  number: number;
  name: string;
  concepts: string[];
}

/**
 * The concepts a query finds, unit by unit, in the syllabus's order.
 *
 * Every word of the query has to be in the name, accents and capitals aside, so «caso b»
 * finds «Caso base» and «base caso» does too. Inside a unit, the names that START with the
 * query come first: somebody typing «rec» wants «Recursividad» before «Llamada recursiva».
 * A query that names a unit brings the whole unit, because a student often remembers the
 * unit and not the word. Pure, so vitest pins it.
 */
export function searchSyllabus(units: SyllabusUnit[], query: string): UnitMatch[] {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const whole = words.join(" ");
  const has = (name: string) => {
    const folded = fold(name);
    return words.every((word) => folded.includes(word));
  };
  return units.flatMap((unit, index) => {
    const found = has(unit.name) ? unit.concepts : unit.concepts.filter(has);
    if (found.length === 0) return [];
    const leading = found.filter((name) => fold(name).startsWith(whole));
    const rest = found.filter((name) => !fold(name).startsWith(whole));
    return [{ number: index + 1, name: unit.name, concepts: [...leading, ...rest] }];
  });
}

/** The index of the unit a concept belongs to, or -1 when the syllabus does not hold it. */
export function unitOf(units: SyllabusUnit[], concept: string | null | undefined): number {
  if (!concept) return -1;
  return units.findIndex((unit) => unit.concepts.includes(concept));
}

/** A syllabus as the API sent it, read defensively: an older API sends none. */
export function unitsOf(payload: { units?: unknown } | null | undefined): SyllabusUnit[] {
  if (!payload || !Array.isArray(payload.units)) return [];
  return payload.units.flatMap((unit) => {
    if (!unit || typeof unit !== "object") return [];
    const { name, concepts } = unit as { name?: unknown; concepts?: unknown };
    if (typeof name !== "string" || !Array.isArray(concepts)) return [];
    const names = concepts.filter((concept): concept is string => typeof concept === "string");
    return names.length > 0 ? [{ name, concepts: names }] : [];
  });
}
