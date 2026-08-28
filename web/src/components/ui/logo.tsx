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
export function Logo({ className, tight = false }: { className?: string; tight?: boolean }) {
  return (
    // `tight` crops the box to the drawing instead of the 24-square the favicons need. The
    // mark is a horizontal band three and a half times wider than it is tall, so in a
    // square box most of what a caller sizes is empty: a lockup that stacks the wordmark
    // under the mark has to be able to make the MARK bigger, not the padding around it.
    //
    // The crop is to the drawing's bounds STROKES INCLUDED, which is the part that bites.
    // The outline square is stroked at 1.6, so it paints 0.8 outside its own rect and
    // reaches x 22.8 / y 15.1; a box ending exactly there loses half that edge, and it is
    // the square carrying «what lies ahead» — the one the whole mark is about.
    <svg
      viewBox={tight ? "1.5 8.7 22 6.6" : "0 0 24 24"}
      fill="none"
      aria-hidden
      className={className}
    >
      <path d="M6.6 12H9.7" stroke="var(--settled)" strokeWidth={1.6} />
      {/* THE STRETCH RUNS IN THE CLEAR GAP, WHICH IS NOT THE GAP BETWEEN THE RECTS.
          The third square is STROKED at 1.6, and a stroke is centred on the path, so it
          paints from 16.6 rather than from its own x of 17.4. A connector drawn to 17.4
          therefore ends 0.8 underneath that edge, and whichever dash landed there fused
          with the square and stuck out to its left. Between 14.3 and 16.6 there are 2.3
          units of actual paper; two marks and their gap take 1.5 of it, centred, so the
          stretch touches neither square — which is the whole point of it being dotted. */}
      <path d="M14.7 12H16.2" stroke="currentColor" strokeWidth={1.6} strokeDasharray="0.5 0.5" />
      <rect x="2" y="9.7" width="4.6" height="4.6" fill="var(--settled)" />
      <rect x="9.7" y="9.7" width="4.6" height="4.6" fill="var(--attention)" />
      <rect x="17.4" y="9.7" width="4.6" height="4.6" stroke="currentColor" strokeWidth={1.6} />
    </svg>
  );
}
