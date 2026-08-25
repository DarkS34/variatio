/**
 * The mark: one node that branches into three variants.
 *
 * It draws what the system does and nothing else — a concept of the graph on the left,
 * solid because it is the thing that exists, and three registers on the right, which are
 * the items derived from it. The three are IDENTICAL on purpose: variants are alternatives
 * of equal standing, not a ranking, and giving one of them a fill would claim otherwise.
 *
 * What the grid changed is HOW the relation is drawn. The earlier mark ran three curved
 * edges from the node to three rings; here there are no connectors at all. A single rule
 * spans exactly the height of the three registers, and the relation is carried by
 * alignment — the node sits on the rule's midline, the three sit against it. That is the
 * same claim the material makes everywhere else: structure is rule and position, not a
 * drawn line for every relation. It also survives being small, which the three curves did
 * not: at 16 px they merged into a smudge.
 *
 * Everything is orthogonal and every corner is square, so the mark cannot drift away from
 * `--radius: 0`. It paints in `currentColor`, so the colour is the caller's (`text-primary`
 * everywhere it appears today, which in this material is the ink) and it inherits the theme
 * instead of pinning a hex the palette would later move.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      aria-hidden
      className={className}
    >
      <rect x="1.8" y="9.1" width="5.8" height="5.8" fill="currentColor" stroke="none" />
      <path d="M11.4 2.4V21.6" />
      <rect x="14.8" y="2.4" width="5.4" height="5.4" />
      <rect x="14.8" y="9.3" width="5.4" height="5.4" />
      <rect x="14.8" y="16.2" width="5.4" height="5.4" />
    </svg>
  );
}
