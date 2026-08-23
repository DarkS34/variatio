import { AlertTriangle, Check, CircleDashed, X } from "lucide-react";
import { Fragment, type ReactNode } from "react";

import { InfoHint } from "@/components/ui/hint";
import { StatusMark } from "@/components/ui/status";
import { Progress } from "@/components/ui/misc";
import { stepExplain } from "@/lib/explain";
import { duration } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StepView } from "@/state/runStore";

// The running step borrows the shape a building stage uses, so "this is the part still
// moving" is drawn the same way here and in the navbar. The other four keep their own
// icons: ok / failed / cancelled are not artifact states and forcing them through the
// chain's table would be claiming they are.
function Icon({ step }: { step: StepView }) {
  if (step.status === "running") return <StatusMark status="building" size="md" />;
  if (step.status === "ok") return <Check className="size-4 text-settled" />;
  if (step.status === "failed") return <AlertTriangle className="size-4 text-destructive" />;
  if (step.status === "cancelled") return <X className="size-4 text-muted-foreground" />;
  return <CircleDashed className="size-4 text-muted-foreground" />;
}

// The line into a SKIPPED step is dotted, for the same reason a rail stretch is: the work
// did not flow through there. There is no "pending" here to dot — a step only enters this
// list once it has started — so skipped is the only break in the sequence there is.
const CONNECTOR = {
  ran: "bg-border",
  skipped: "bg-[repeating-linear-gradient(to_bottom,var(--border)_0_3px,transparent_3px_6px)]",
};

function Insert({ children, last }: { children: ReactNode; last: boolean }) {
  return (
    <li className="flex gap-3 px-2 py-0.5">
      <div className="flex w-4 shrink-0 justify-center">
        {last ? null : <span className="w-px flex-1 bg-border" />}
      </div>
      <div className="min-w-0 flex-1 pb-1">{children}</div>
    </li>
  );
}

interface StepGroup extends StepView {
  runs: number;
}

// A build repeats the same step once per document — transcribing, extracting batches,
// tagging — and a run that processes twenty documents used to draw sixty rows. One row
// per step id says the same thing in the space of one: the label and bar follow the
// LATEST occurrence (the document in progress), `runs` counts how many came before, and
// the duration is the sum of all of them.
function groupSteps(steps: StepView[]): StepGroup[] {
  const order: string[] = [];
  const occurrences = new Map<string, StepView[]>();
  for (const step of steps) {
    if (!occurrences.has(step.id)) {
      occurrences.set(step.id, []);
      order.push(step.id);
    }
    occurrences.get(step.id)!.push(step);
  }
  return order.map((id) => {
    const runs = occurrences.get(id)!;
    const last = runs[runs.length - 1];
    const status =
      last.status === "running"
        ? "running"
        : runs.some((s) => s.status === "failed")
          ? "failed"
          : last.status;
    const measured = runs.filter((s) => s.ms !== undefined);
    const ms =
      measured.length > 0
        ? measured.reduce((total, s) => total + (s.ms ?? 0), 0)
        : undefined;
    const error = runs.map((s) => s.error).filter(Boolean).at(-1) ?? null;
    return { ...last, key: id, status, ms, error, runs: runs.length };
  });
}

// Evidence a step consumed, shown where it was produced instead of in a pile below the
// timeline: `slots[id]` is rendered just before the step with that id, and after the
// last step while that step has not started yet.
export function RunTimeline({
  steps: rawSteps,
  className,
  slots,
}: {
  steps: StepView[];
  className?: string;
  slots?: Record<string, ReactNode>;
}) {
  const steps = groupSteps(rawSteps);
  const pending = Object.entries(slots ?? {}).filter(
    ([id, node]) => node && !steps.some((step) => step.id === id),
  );

  if (steps.length === 0 && pending.length === 0) {
    return (
      <p className={cn("text-body text-muted-foreground", className)}>Sin pasos todavía.</p>
    );
  }

  return (
    <ol className={cn("space-y-1", className)}>
      {steps.map((step, index) => {
        const slot = slots?.[step.id];
        const running = step.status === "running";
        const hasBar = running && Boolean(step.total);
        const explain = stepExplain(step.id);
        return (
          <Fragment key={step.key}>
            {slot ? <Insert last={false}>{slot}</Insert> : null}
            <li
              className={cn(
                "relative flex gap-3 rounded-md px-2 py-1.5 transition-colors",
                running && "bg-accent/60",
              )}
            >
              <div className="flex flex-col items-center">
                <Icon step={step} />
                {index < steps.length - 1 ? (
                  <span
                    className={cn(
                      "mt-1 w-px flex-1",
                      steps[index + 1].status === "skipped" ? CONNECTOR.skipped : CONNECTOR.ran,
                    )}
                  />
                ) : null}
              </div>

              <div className="min-w-0 flex-1 pb-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span
                      className={cn(
                        "truncate text-body",
                        running ? "font-medium" : "text-muted-foreground",
                        step.status === "failed" && "text-destructive",
                      )}
                    >
                      {step.label}
                    </span>
                    {/* The (i) only while the sentence is NOT in view. The running step already prints it in
                        full under the title, so there the icon was a second copy of the same sentence a
                        centimetre from the first: when both say the same thing, the visible one stays. */}
                    {explain && !running ? (
                      <InfoHint label={`Qué hace: ${step.label}`}>{explain}</InfoHint>
                    ) : null}
                  </span>
                  <span className="shrink-0 text-small nums text-muted-foreground">
                    {step.runs > 1 ? <span className="mr-2">×{step.runs}</span> : null}
                    {step.total && (running || step.runs === 1) ? (
                      <>
                        {step.current ?? 0}/{step.total}
                      </>
                    ) : null}
                    {step.ms !== undefined && !running ? (
                      <span className="ml-2">{duration(step.ms)}</span>
                    ) : null}
                  </span>
                </div>

                {running && explain ? (
                  <p className="text-small leading-relaxed text-muted-foreground">{explain}</p>
                ) : null}
                {step.detail ? (
                  <p className="truncate text-small text-muted-foreground">{step.detail}</p>
                ) : null}
                {step.error ? <p className="text-small text-destructive">{step.error}</p> : null}
                {hasBar ? (
                  <Progress value={step.current ?? 0} max={step.total} className="mt-1.5" />
                ) : null}
              </div>
            </li>
          </Fragment>
        );
      })}

      {pending.map(([id, node]) => (
        <Insert key={id} last>
          {node}
        </Insert>
      ))}
    </ol>
  );
}
