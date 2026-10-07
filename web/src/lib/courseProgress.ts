/**
 * How far a class has got, unit by unit, in the order of the syllabus.
 *
 * The course's progress is a list of concepts (`server/curriculum.py`); what a teacher reads
 * is where it stands in each unit: «Tema 2 · 4 de 6».
 */
export interface UnitProgress {
  name: string;
  total: number;
  covered: number;
}

/** Count the concepts covered in each unit, keeping the syllabus' order of units. */
export function progressByUnit(
  units: { name: string; concepts: string[] }[],
  covered: string[],
): UnitProgress[] {
  const seen = new Set(covered);
  return units.map((unit) => ({
    name: unit.name,
    total: unit.concepts.length,
    covered: unit.concepts.filter((concept) => seen.has(concept)).length,
  }));
}
