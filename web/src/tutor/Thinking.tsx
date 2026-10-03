import { Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import type { Pending } from "./types";

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

/**
 * THE REPLY ON ITS WAY: A QUESTION BEING WRITTEN.
 *
 * What the student waits for is a question — the tutor answers with one every time — so the
 * sign of waiting is a question mark written square by square, in the squares the app's own
 * mark is made of, and unwritten again while the reply is not there. Its dot is the one
 * coloured square: the thing to act on is about to arrive.
 *
 * Beside it, one line says what is happening and one says why it takes a moment and arrives
 * whole: a reply is checked against the method before anybody reads it. Nothing here claims
 * a step the screen does not know — a turn's job tells the workspace's stream no detail —
 * so the text is the same from start to end.
 *
 * A queued reply is not a running one: its mark is hollow and still.
 */
export function Thinking({ pending, onStop }: { pending: Pending; onStop: () => void }) {
  const { t } = useT();
  const queued = pending.status === "queued";
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-4 gap-y-2 border-l-2 border-border py-1 pl-4">
      <QuestionMark live={!queued} />
      <div className="min-w-0 flex-1 basis-56 space-y-0.5">
        <p className="font-medium">{t(queued ? "tutor.pending.queued" : "tutor.pending.running")}</p>
        <p className="max-w-prose text-small text-muted-foreground">
          {queued
            ? pending.queue_position > 1
              ? t("tutor.pending.queuedAhead", { n: pending.queue_position - 1 })
              : t("tutor.pending.queuedNext")
            : t("tutor.pending.runningWhy")}
        </p>
      </div>
      <Button variant="ghost" size="sm" onClick={onStop}>
        <Square />
        {t("tutor.pending.stop")}
      </Button>
    </div>
  );
}

function QuestionMark({ live }: { live: boolean }) {
  return (
    <div aria-hidden className="grid shrink-0 grid-cols-[repeat(5,6px)] grid-rows-[repeat(7,6px)] gap-px">
      {[...STROKE, DOT].map(([column, row], index) => (
        <span
          key={`${column}-${row}`}
          style={{
            gridColumn: column,
            gridRow: row,
            animationDelay: live ? `${index * BEAT_MS}ms` : undefined,
          }}
          className={cn(
            live
              ? ["animate-square-write", index === STROKE.length ? "bg-attention" : "bg-foreground"]
              : "border border-muted-foreground",
          )}
        />
      ))}
    </div>
  );
}
