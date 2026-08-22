/**
 * The mark: one node that branches into three variants.
 *
 * It draws what the system does and nothing else — a concept of the graph on the left,
 * solid because it is the thing that exists, and three rings on the right, which are the
 * items derived from it. The three are IDENTICAL on purpose: variants are alternatives of
 * equal standing, not a ranking, and giving one of them a fill would claim otherwise.
 *
 * It paints in `currentColor`, so the colour is the caller's (`text-primary` everywhere it
 * appears today) and it inherits the theme instead of pinning a hex that the palette would
 * later drift away from. The edges stop short of the rings rather than running under them,
 * which is what lets it sit on any surface with no knowledge of the one behind it.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      aria-hidden
      className={className}
    >
      <path d="M7.5 10.3C10.4 7.4 13 5.9 16.1 5.5" />
      <path d="M8.2 12H16.9" />
      <path d="M7.5 13.7C10.4 16.6 13 18.1 16.1 18.5" />
      <circle cx="4.9" cy="12" r="3" fill="currentColor" stroke="none" />
      <circle cx="18.6" cy="5.4" r="2.2" />
      <circle cx="19.3" cy="12" r="2.2" />
      <circle cx="18.6" cy="18.6" r="2.2" />
    </svg>
  );
}
