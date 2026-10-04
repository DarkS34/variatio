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
        // rows, two tints of the same ink are the same badge twice; filled, the label reads at
        // 11.3:1 in light and 6.4:1 in dark. It is a figure/ground inversion and not a hue, so
        // it survives greyscale and every colour vision, and the pair is the ink as a fill,
        // `--ink`/`--ink-foreground`, which `check:color` verifies in both themes (the text
        // ink in dark is a pale sea, and filled with it a badge was a white chip). Same as
        // `ConceptChip`'s `primary` tone, deliberately: the primary concept looks the same
        // wherever it is read, and which of the two components draws it is decided by the
        // room available and never by the meaning.
        primary: "border-transparent bg-ink text-ink-foreground",
        // A hairline pill: on the clay a `--secondary` fill is the clay itself.
        secondary: "border-border text-secondary-foreground",
        outline: "border-border text-muted-foreground",
        settled:
          "border-transparent bg-[color-mix(in_oklch,var(--settled)_8%,transparent)] text-settled",
        attention:
          "border-transparent bg-[color-mix(in_oklch,var(--attention)_8%,transparent)] text-attention",
        danger: "border-transparent bg-destructive/8 text-destructive",
        // An optional function named outside its own screen, in its own colour as its door
        // is: a destination, not a state. The same 8 % as every tint above.
        evaluation:
          "border-transparent bg-[color-mix(in_oklab,var(--evaluation)_8%,transparent)] text-evaluation",
        tutor:
          "border-transparent bg-[color-mix(in_oklab,var(--tutor)_8%,transparent)] text-tutor",
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
