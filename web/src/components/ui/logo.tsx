import { cn } from "@/lib/utils";

/**
 * The mark: the knowledge frontier, in three squares.
 *
 * What is behind you, solid in `--settled`; where you act, solid in the one ultramarine the
 * palette spends on "act here"; what lies ahead, an outline. It draws the calculation the
 * generator performs on every prompt, so the mark introduces no colour of its own.
 *
 * The three squares are the same size and the same distance apart, and the outline one is
 * INSET BY HALF ITS STROKE: a stroke is centred on the path, so a 4.6 rect stroked at 1.6
 * paints 6.2 across and overhangs the band. Drawn as a 3.4 rect at 18.0/10.3 it paints
 * exactly the 4.6 box the other two fill, with every gap 3.1.
 *
 * The stroke is 1.2, which is what opens the counter to 2.2: the outer box is fixed at 4.6
 * by its neighbours, so the only way to widen the hole is to thin the rule. These three
 * numbers are a property of the whole mark and not of one file — the two favicons carry
 * them too, and getting one wrong is a square of a different size in the tab strip.
 *
 * The coloured stops read their tokens directly and move with the theme; the outline paints
 * in `currentColor`, so a caller's `text-primary` owns it. Everything is orthogonal and
 * every corner square, so the mark cannot drift from `--radius: 0`.
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
      <rect x="18" y="10.3" width="3.4" height="3.4" stroke="currentColor" strokeWidth={1.2} />
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
    <span className={cn("flex justify-center flex-col items-center gap-1 leading-none", className)}>
      <Logo tight className="h-[0.67rem] w-[2.9rem] text-primary" />
      {/* The tracking of `text-micro` (0.12em) is added after the LAST letter too, so the
          word paints left of its own box and the two halves of the lockup do not line up:
          measured at 8x on the login screen, the mark's ink sat 0.875 px right of the
          word's. Taking the trailing space back off the box is what `items-center` then
          centres. */}
      <span
        className={cn(
          "text-micro font-condensed uppercase [margin-inline-end:-0.12em]",
          compact && "hidden lg:inline",
        )}
      >
        Variatio
      </span>
    </span>
  );
}
