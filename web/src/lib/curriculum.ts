// Mirrors `variant_generator.assumed_known` / `forbidden`. The server narrows both closures
// by the curriculum in force BEFORE writing them into the prompt, so a panel that drew the
// bare closures would name one set of prerequisites while the prompt named another. The two
// operations are not interchangeable — intersection on the permissive side, subtraction on
// the restrictive one — and swapping them would mark as known exactly the prerequisites the
// student has not seen. An empty or absent curriculum narrows nothing, as `if curriculum:`
// does on the other side.
export function assumedKnown(closure: string[], curriculum: string[] | null): string[] {
  if (!curriculum || curriculum.length === 0) return closure;
  const covered = new Set(curriculum);
  return closure.filter((name) => covered.has(name));
}

export function notYetTaught(closure: string[], curriculum: string[] | null): string[] {
  if (!curriculum || curriculum.length === 0) return closure;
  const covered = new Set(curriculum);
  return closure.filter((name) => !covered.has(name));
}
