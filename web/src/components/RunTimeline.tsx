import { AlertTriangle, Check, CircleDashed, Cpu, Loader2, X } from "lucide-react";

import { Progress } from "@/components/ui/misc";
import { duration } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StepView } from "@/state/runStore";

function Icon({ step }: { step: StepView }) {
  if (step.status === "running") {
    return step.kind === "model" ? (
      <Cpu className="size-4 animate-pulse-soft text-[var(--info)]" />
    ) : (
      <Loader2 className="size-4 animate-spin text-[var(--info)]" />
    );
  }
  if (step.status === "ok") return <Check className="size-4 text-[var(--success)]" />;
  if (step.status === "failed") return <AlertTriangle className="size-4 text-destructive" />;
  if (step.status === "cancelled") return <X className="size-4 text-muted-foreground" />;
  return <CircleDashed className="size-4 text-muted-foreground" />;
}

export function RunTimeline({ steps, className }: { steps: StepView[]; className?: string }) {
  if (steps.length === 0) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>
        Todavía no ha empezado ningún paso.
      </p>
    );
  }

  return (
    <ol className={cn("space-y-1", className)}>
      {steps.map((step, index) => {
        const running = step.status === "running";
        const hasBar = running && Boolean(step.total);
        return (
          <li
            key={step.key}
            className={cn(
              "relative flex gap-3 rounded-md px-2 py-1.5 transition-colors",
              running && "bg-accent/60",
            )}
          >
            <div className="flex flex-col items-center">
              <Icon step={step} />
              {index < steps.length - 1 ? <span className="mt-1 w-px flex-1 bg-border" /> : null}
            </div>

            <div className="min-w-0 flex-1 pb-1">
              <div className="flex items-baseline justify-between gap-3">
                <p
                  className={cn(
                    "truncate text-sm",
                    running ? "font-medium" : "text-muted-foreground",
                    step.status === "failed" && "text-destructive",
                  )}
                >
                  {step.label}
                </p>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {step.total ? (
                    <>
                      {step.current ?? 0}/{step.total}
                    </>
                  ) : null}
                  {step.ms !== undefined && !running ? (
                    <span className="ml-2">{duration(step.ms)}</span>
                  ) : null}
                </span>
              </div>

              {step.detail ? (
                <p className="truncate text-xs text-muted-foreground">{step.detail}</p>
              ) : null}
              {step.error ? <p className="text-xs text-destructive">{step.error}</p> : null}
              {hasBar ? (
                <Progress value={step.current ?? 0} max={step.total} className="mt-1.5" />
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
