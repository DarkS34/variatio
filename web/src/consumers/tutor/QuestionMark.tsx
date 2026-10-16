import { cn } from "@/lib/utils";

// A question mark on a grid of five columns by seven rows, as the squares that draw it, in
// the order a hand would write it: the hook from its left tip round to the stem, then the dot.
const STROKE: ReadonlyArray<readonly [number, number]> = [
  [1, 2],
  [2, 1],
  [3, 1],
  [4, 1],
  [5, 2],
  [5, 3],
  [4, 4],
  [3, 5],
];
const DOT = [3, 7] as const;
const BEAT_MS = 130;

/** What the mark says: a question to answer now, one already answered, or one on its way. */
export type QuestionMarkTone = "attention" | "settled" | "writing" | "queued";

/**
 * THE TUTOR'S OWN SIGN: A QUESTION MARK MADE OF THE APP'S SQUARES.
 *
 * Every reply ends by asking, so one sign stands for what the tutor does, at its three
 * moments. While the reply is on its way (`writing`) the mark is written square by square
 * and unwritten again, its dot the one coloured square: the thing to act on is about to
 * arrive. Queued, it is hollow and still. Once the reply is there, the same mark stands
 * beside the question it closes with — ink with the coral dot on the question to answer
 * now (`attention`), and settled grey on every question already answered (`settled`), so
 * one dot on the screen says where the conversation is.
 *
 * `size` is the side of one square in pixels: six beside a line of status, five beside a
 * question set in the heading's size.
 */
export function QuestionMark({
  tone,
  size = 6,
  className,
}: {
  tone: QuestionMarkTone;
  size?: number;
  className?: string;
}) {
  const writing = tone === "writing";
  return (
    <div
      aria-hidden
      style={{
        gridTemplateColumns: `repeat(5, ${size}px)`,
        gridTemplateRows: `repeat(7, ${size}px)`,
      }}
      className={cn("grid shrink-0 gap-px", className)}
    >
      {[...STROKE, DOT].map(([column, row], index) => {
        const dot = index === STROKE.length;
        return (
          <span
            key={`${column}-${row}`}
            style={{
              gridColumn: column,
              gridRow: row,
              animationDelay: writing ? `${index * BEAT_MS}ms` : undefined,
            }}
            className={cn(
              tone === "queued" && "border border-muted-foreground",
              tone === "settled" && "bg-settled",
              (tone === "attention" || writing) && (dot ? "bg-attention-fill" : "bg-foreground"),
              writing && "animate-square-write",
            )}
          />
        );
      })}
    </div>
  );
}
