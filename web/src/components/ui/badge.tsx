import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-micro font-condensed uppercase transition-colors [&_svg]:size-3",
  {
    variants: {
      // Every tint is 8 %, and the number is measured rather than chosen. A badge paints
      // its own hue behind its own text, so the tint eats the contrast the token was
      // verified at: settled and attention were at 18 %, which in light mode dropped them
      // to 4.32 and 4.26 — under the 4.5 floor, on the badge that reports the state of
      // every stage. What sets the ceiling is not those two but --destructive in dark
      // mode, which is why one value rather than one per hue.
      variant: {
        default: "border-transparent bg-primary/8 text-primary",
        // THE ONE VARIANT THAT IS NOT A TINT, and it is exempt for a reason rather than by
        // oversight: every other variant reports a STATE in its own hue, where this one
        // separates ONE badge from its siblings — the primary concept of an exercise among
        // the concepts it merely uses. A tint cannot do that. Measured on the bank's own
        // rows, `default` against `secondary` is **1.03:1** of ground and 1.10:1 of text,
        // which is the same badge twice; filled it is **15.88:1**, and the text on it
        // 17.34:1. It is a figure/ground inversion and not a hue, so it survives greyscale
        // and every colour vision, and the pair is `--primary`/`--primary-foreground`,
        // which `check:color` already verifies in both themes. It is the same drawing as
        // `ConceptChip`'s `primary` tone, deliberately: the primary concept looks the same
        // wherever it is read, and which of the two components draws it is decided by the
        // room available and never by the meaning.
        primary: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-muted-foreground",
        settled:
          "border-transparent bg-[color-mix(in_oklch,var(--settled)_8%,transparent)] text-settled",
        attention:
          "border-transparent bg-[color-mix(in_oklch,var(--attention)_8%,transparent)] text-attention",
        danger: "border-transparent bg-destructive/8 text-destructive",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
  /** The state's shape, when the badge is a stage's. Colour cannot be the only channel,
   *  and a badge carrying text AND a shape says it twice without taking more room. */
  mark?: ReactNode;
}

export function Badge({
  className,
  variant,
  mark,
  children,
  ...props
}: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {mark}
      {children}
    </span>
  );
}

export { badgeVariants };
