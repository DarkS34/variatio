import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-micro font-condensed uppercase transition-colors [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/12 text-primary",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-muted-foreground",
        settled: "border-transparent bg-[color-mix(in_oklch,var(--settled)_18%,transparent)] text-settled",
        attention:
          "border-transparent bg-[color-mix(in_oklch,var(--attention)_18%,transparent)] text-attention",
        danger: "border-transparent bg-destructive/15 text-destructive",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** The state's shape, when the badge is a stage's. Colour cannot be the only channel,
   *  and a badge carrying text AND a shape says it twice without taking more room. */
  mark?: ReactNode;
}

export function Badge({ className, variant, mark, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {mark}
      {children}
    </span>
  );
}

export { badgeVariants };
