import {
  FlaskConical,
  MessageCircleQuestion,
  MessagesSquare,
  WandSparkles,
  type LucideIcon,
} from "lucide-react";

import type { Door } from "@/lib/steps";
import { cn } from "@/lib/utils";

/**
 * THE FIGURE OF EACH FUNCTION, one home for the bar, «Funciones», the panel and the badges.
 *
 * Chosen to say what the function does (the user's request, 2026-11-04): a wand that makes
 * exercises, a flask for the study that measures the system, a question in a bubble for the
 * tutor that answers with questions, two bubbles for the free chat. Until then a play button,
 * scales and two sorts of bubble that read as one.
 */
export const FUNCTION_ICONS: Record<Door["key"], LucideIcon> = {
  generate: WandSparkles,
  compare: FlaskConical,
  tutor: MessageCircleQuestion,
  chat: MessagesSquare,
};

const SIZE = {
  // The bar's box, the size a step's number is drawn in (`StepCounter.COUNTER_BOX`).
  sm: { box: "size-[22px] rounded-sm", icon: "size-3.5" },
  // A row of the panel's list: the 16 px mark of every `Sections` row.
  md: { box: "size-4 rounded-sm", icon: "size-3" },
  // A card of «Funciones».
  lg: { box: "size-12 rounded-inner", icon: "size-6" },
} as const;

/**
 * A function's icon on a tile of the function's colour: the same mark wherever a function is
 * named. Flat, a tint and never a relief, because it is a small thing (`DESIGN.md` §1).
 * Locked, it is the dashed outline a step not reachable yet has.
 */
export function FunctionMark({
  door,
  size = "sm",
  locked = false,
  className,
}: {
  door: Door["key"];
  size?: keyof typeof SIZE;
  locked?: boolean;
  className?: string;
}) {
  const Icon = FUNCTION_ICONS[door];
  const measure = SIZE[size];
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center",
        measure.box,
        locked
          ? "border border-dashed border-input text-muted-foreground"
          : "bg-[color-mix(in_oklab,var(--function)_16%,transparent)] text-function",
        className,
      )}
    >
      <Icon className={measure.icon} strokeWidth={2.25} />
    </span>
  );
}
