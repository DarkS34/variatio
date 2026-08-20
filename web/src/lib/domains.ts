import { domainColour } from "@/lib/format";
import type { KgConcept } from "@/lib/types";

/** Reproduces `server/kg_view.build`'s group order (-size, name), which fixes the colours. */
export function domainColours(concepts: KgConcept[]): Map<string, string> {
  const sizes = new Map<string, number>();
  for (const concept of concepts) {
    sizes.set(concept.domain, (sizes.get(concept.domain) ?? 0) + 1);
  }
  const ordered = [...sizes.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es"),
  );
  return new Map(ordered.map(([name], index) => [name, domainColour(index, ordered.length)]));
}
