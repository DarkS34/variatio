import { cn } from "@/lib/utils";

/**
 * The mark: the knowledge frontier, in three squares.
 *
 * Three concepts in a row — what is behind you, solid in `--settled`; where you act,
 * solid in the one ultramarine the palette spends on «act here»; what lies ahead, an
 * outline. It draws the calculation the generator performs on every prompt (assumed
 * known / target / not yet taught), which is the same thing the palette encodes
 * everywhere else — so the mark introduces no colour of its own.
 *
 * The three squares are the same size and the same distance apart (2026-08-31, explicit
 * user request), which took two changes rather than one: the connectors between them are
 * gone, and the third square is INSET BY HALF ITS STROKE. A stroke is centred on the
 * path, so a 4.6 rect stroked at 1.6 paints 6.2 across — the outline square was visibly
 * larger than its two solid neighbours and overhung the band above and below. Drawn as a
 * 3.0 rect at 18.2/10.5 it paints exactly the 4.6 box the other two fill, and every gap
 * is 3.1.
 *
 * The two coloured stops read their tokens directly (`var(--settled)`, `var(--attention)`)
 * and therefore move with the theme; the outline paints in `currentColor`, so the caller's
 * `text-primary` still owns it. Everything is orthogonal and every corner is square, so
 * the mark cannot drift away from `--radius: 0`.
 *
 * The favicons carry the single-tone version: fill against outline keeps the frontier
 * legible without colour.
 */
export function Logo({ className, tight = false }: { className?: string; tight?: boolean }) {
  return (
    // `tight` crops the box to the drawing instead of the 24-square the favicons need. The
    // mark is a horizontal band more than four times wider than it is tall, so in a square
    // box most of what a caller sizes is empty: a lockup that stacks the wordmark under
    // the mark has to be able to make the MARK bigger, not the padding around it.
    //
    // With the outline square inset, the crop is exactly the band — 2 to 22 across, 9.7 to
    // 14.3 down — strokes included, because no stroke paints outside it any more. That is
    // flatter than the box this replaced (which had to clear the outline's overhang), so
    // `Lockup` sizes the mark by its width and lets the height follow the ratio.
    <svg
      viewBox={tight ? "2 9.7 20 4.6" : "0 0 24 24"}
      fill="none"
      aria-hidden
      className={className}
    >
      <rect x="2" y="9.7" width="4.6" height="4.6" fill="var(--settled)" />
      <rect x="9.7" y="9.7" width="4.6" height="4.6" fill="var(--attention)" />
      <rect x="18.2" y="10.5" width="3" height="3" stroke="currentColor" strokeWidth={1.6} />
    </svg>
  );
}

/**
 * The lockup: the mark with the wordmark set under it.
 *
 * It is the application's identity wherever the application names itself, and it exists
 * as one component because it was drawn three different ways — the navbar stacked it and
 * the two screens rendered before a session put the 24-square mark beside the word, where
 * the band is a strip floating in the middle of an empty box. The stacked form is the one
 * that survives: it lets the MARK be the larger half without spending the width a
 * horizontal lockup takes on a header's centre line.
 *
 * `compact` is the navbar's alone: below `lg` a 360 px header has room for the mark and
 * nothing else. A screen whose only identity is this one always says the name.
 */
export function Lockup({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("flex flex-col items-center gap-1 leading-none", className)}>
      {/* SIZED BY WIDTH, and the height is the band's own ratio (20 : 4.6). The mark
          keeps the 2.9rem it always had in the header — nothing moves sideways — and
          the squares come out slightly taller than before, because the box no longer
          has to reserve the overhang of a stroke. A height that does not match the
          ratio only letterboxes: `meet` would centre the band and leave dead space
          between it and the wordmark. */}
      <Logo tight className="h-[0.67rem] w-[2.9rem] text-primary" />
      <span className={cn("text-micro font-condensed uppercase", compact && "hidden lg:inline")}>
        Variatio
      </span>
    </span>
  );
}
