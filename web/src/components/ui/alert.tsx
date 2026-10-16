import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Alert({
  tone = "info",
  title,
  children,
  className,
  action,
}: {
  tone?: "info" | "attention" | "danger" | "settled";
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  const tones = {
    // "info" survives as the name of a TONE even though the --info token is gone: a
    // neutral notice is painted with the primary, which is what already means "this is
    // the system talking", not "something is wrong".
    info: "border-primary/35 bg-primary/[0.08]",
    attention:
      "border-[color-mix(in_oklch,var(--attention)_40%,transparent)] bg-[color-mix(in_oklch,var(--attention)_10%,transparent)]",
    danger: "border-destructive/40 bg-destructive/10",
    settled:
      "border-[color-mix(in_oklch,var(--settled)_35%,transparent)] bg-[color-mix(in_oklch,var(--settled)_10%,transparent)]",
  }[tone];

  return (
    <div className={cn("flex items-start gap-3 rounded-lg border p-3 text-body", tones, className)}>
      <div className="min-w-0 flex-1">
        {title ? <p className="font-medium">{title}</p> : null}
        {children ? <div className="text-muted-foreground [&_p]:mt-1">{children}</div> : null}
      </div>
      {action}
    </div>
  );
}
