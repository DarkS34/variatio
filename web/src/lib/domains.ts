import { domainColour } from "@/lib/format";
import type { KgConcept } from "@/lib/types";

/**
 * Colour by the domain's place in the syllabus. `KnowledgeGraph.all_concepts` walks
 * `concepts_by_domains`, and `kg_edit.summary` walks that, so a domain's FIRST appearance
 * in this array is its position in the temario — nothing is re-sorted here. It used to be
 * sorted by size, which meant that a rebuild moving one concept could swap two domains'
 * colours, and that "consecutive in the legend" meant "of similar size" rather than
 * "Tema I next to Tema II", which is the pair the ramp was measured to separate.
 */
export function domainColours(concepts: KgConcept[]): Map<string, string> {
  const order: string[] = [];
  const seen = new Set<string>();
  for (const concept of concepts) {
    if (seen.has(concept.domain)) continue;
    seen.add(concept.domain);
    order.push(concept.domain);
  }
  return new Map(order.map((name, index) => [name, domainColour(index, order.length)]));
}
