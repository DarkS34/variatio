import { Check, Loader2 } from "lucide-react";

import type { StepState } from "@/lib/steps";
import { cn } from "@/lib/utils";

/**
 * The step's number, in a box whose stroke says where you stand.
 *
 * The strokes are the palette's frontier and not a traffic light: a fill in `--attention`
 * where you act, a dashed outline on what is not reachable yet, a bare tick on what is
 * behind you. The wheel of a running step is `--primary` plus motion, and it is
 * deliberately not switched off under `prefers-reduced-motion`: it is the one sign in the
 * bar that a build running for an hour is still alive.
 */
export function StepCounter({
  state,
  n,
  busy = false,
}: {
  state: StepState;
  n: string;
  busy?: boolean;
}) {
  if (busy) {
    return (
      <span className={cn(COUNTER_BOX, "text-primary")}>
        <Loader2 className="size-4 animate-spin" strokeWidth={2.5} />
      </span>
    );
  }
  return (
    <span
      className={cn(
        COUNTER_BOX,
        "nums font-condensed text-small font-semibold",
        // A box says "there is something here to reach", so what is behind you carries
        // none. `COUNTER_BOX` stays either way, or the four stops stop lining up.
        state === "done" && "text-settled",
        state === "now"
          // The TOKEN and not its light-mode value: `--attention` is a light ground in dark
          // mode, so a literal puts a near-white number on it. `check:color` cannot see
          // this — it reads `index.css`, not a class in a component.
          ? "bg-attention-fill text-attention-fill-foreground"
          : null,
        state === "later" && "border border-dashed border-input text-muted-foreground",
      )}
    >
      {state === "done" ? <Check className="size-3.5" strokeWidth={3} aria-hidden /> : n}
    </span>
  );
}

// `min-w` and not a fixed square: "1" and an icon are the same height, and the height is
// what keeps the names of a row on one line.
export const COUNTER_BOX = "flex h-[22px] min-w-[20px] shrink-0 items-center justify-center rounded-sm px-1";
