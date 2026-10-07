import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function Card({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn("surface", className)}
        {...props}
      />
    );
  },
);

/**
 * A block's head: its title, the sentence right under it (4 px, as a section's), and 16 px to
 * what the block holds. One measure for every block (2026-10-07): the heads of «Motor» left 8,
 * the panel's settings 12 and «Tipos de ejercicio» 20, each overriding the bottom on its own.
 */
export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  // A head with nothing under it closes the block at the block's own 20 px: alone, or
  // followed by a content that holds nothing (which then draws nothing).
  return (
    <div
      className={cn("flex flex-col gap-1 p-5 pb-4 last:pb-5 [&:has(+:empty)]:pb-5", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-heading", className)} {...props} />;
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-small text-muted-foreground", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-0 empty:hidden", className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center gap-2 p-5 pt-0", className)} {...props} />;
}
