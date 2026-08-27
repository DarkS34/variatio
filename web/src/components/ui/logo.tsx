/**
 * The mark: the knowledge frontier, on one rule.
 *
 * Three concepts in a row — what is behind you, solid in `--settled`; where you act,
 * solid in the one ultramarine the palette spends on «act here»; what lies ahead, an
 * outline reached through a dotted stretch. It draws the calculation the generator
 * performs on every prompt (assumed known / target / not yet taught), which is the same
 * thing the palette encodes everywhere else — so the mark introduces no colour of its own.
 *
 * The two coloured stops read their tokens directly (`var(--settled)`, `var(--attention)`)
 * and therefore move with the theme; the ink parts — the dotted stretch and the outline —
 * paint in `currentColor`, so the caller's `text-primary` still owns them. Everything is
 * orthogonal and every corner is square, so the mark cannot drift away from `--radius: 0`.
 *
 * The favicons carry the single-tone version: fill against outline and the dotted stretch
 * keep the frontier legible without colour.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className={className}>
      <path d="M6.6 12H9.7" stroke="var(--settled)" strokeWidth={1.6} />
      <path d="M14.3 12H17.4" stroke="currentColor" strokeWidth={1.6} strokeDasharray="1.1 1.6" />
      <rect x="2" y="9.7" width="4.6" height="4.6" fill="var(--settled)" />
      <rect x="9.7" y="9.7" width="4.6" height="4.6" fill="var(--attention)" />
      <rect x="17.4" y="9.7" width="4.6" height="4.6" stroke="currentColor" strokeWidth={1.6} />
    </svg>
  );
}
