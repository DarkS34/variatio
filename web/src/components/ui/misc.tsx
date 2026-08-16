import { Check, Loader2, Minus } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Separator({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("h-px w-full bg-border", className)} {...props} />;
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse-soft rounded-md bg-muted", className)} {...props} />;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} />;
}

export function Progress({
  value,
  max,
  className,
  tone = "primary",
}: {
  value: number;
  max?: number | null;
  className?: string;
  tone?: "primary" | "success" | "warning" | "danger";
}) {
  const indeterminate = !max || max <= 0;
  const pct = indeterminate ? 0 : Math.min(100, Math.round((value / max) * 100));
  const colour = {
    primary: "bg-primary",
    success: "bg-[var(--success)]",
    warning: "bg-[var(--warning)]",
    danger: "bg-destructive",
  }[tone];

  return (
    <div
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={indeterminate ? undefined : 100}
      aria-valuenow={indeterminate ? undefined : pct}
    >
      <div
        className={cn(
          "h-full rounded-full",
          colour,
          indeterminate ? "w-1/3 animate-progress-sweep" : "transition-[width] duration-300 ease-out",
        )}
        style={indeterminate ? undefined : { width: `${pct}%` }}
      />
    </div>
  );
}

/**
 * The same 0-100 as `Progress`, cut into the phases that produce it.
 *
 * A single bar answers «how much is left» and nothing else; a build is seven very
 * different jobs in a row, and which one it is stuck on is half of what you want to
 * know. Each segment is as wide as that phase's share of the plan — the builders'
 * measured weights — so the bar keeps being an honest picture of the time, not a row
 * of equal boxes that suggests seven equal stages.
 *
 * Three states, one colour each: done, running (which pulses, because that is the only
 * part still moving) and pending. The fill inside the running segment is the same
 * percentage the plain bar would have shown.
 */
export function PhaseBar({
  phases,
  percent,
  activeKey,
  live = true,
  className,
}: {
  phases: { key: string; label: string; weight: number; seconds?: number }[];
  percent: number;
  activeKey?: string | null;
  live?: boolean;
  className?: string;
}) {
  const total = phases.reduce((sum, phase) => sum + phase.weight, 0) || 1;
  let cumulative = 0;

  return (
    <div
      className={cn("flex w-full items-center gap-[3px]", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(percent)}
    >
      {phases.map((phase) => {
        const start = (cumulative / total) * 100;
        const span = (phase.weight / total) * 100;
        cumulative += phase.weight;

        const fill = Math.min(1, Math.max(0, (percent - start) / span));
        // The event says which phase is running; the percentage only decides it when no
        // event has arrived yet, and it gets the boundaries wrong exactly when a phase
        // costs nothing and is skipped in the same millisecond it starts.
        const running =
          live && (activeKey ? phase.key === activeKey : fill > 0 && fill < 1);

        return (
          <div
            key={phase.key}
            title={phase.label}
            // A phase worth 1 % of the plan is 2 px wide in a sidebar card, which reads as
            // a rendering glitch rather than as a cheap phase. The floor costs the wide
            // segments a pixel each and keeps every section of the plan visible.
            style={{ flexGrow: phase.weight, minWidth: 5 }}
            className={cn(
              "relative h-1.5 overflow-hidden rounded-full",
              running ? "bg-primary/20" : "bg-muted",
              running && "animate-pulse-soft",
            )}
          >
            <div
              className={cn(
                "relative h-full overflow-hidden rounded-full transition-[width] duration-500 ease-out",
                fill >= 1 ? "bg-[var(--success)]" : "bg-primary",
              )}
              style={{ width: `${fill * 100}%` }}
            >
              {running && fill > 0 ? (
                <span className="absolute inset-y-0 w-1/3 animate-progress-sweep bg-[color-mix(in_oklch,var(--card)_55%,transparent)]" />
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Switch({
  checked,
  onCheckedChange,
  disabled,
  label,
}: {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
        checked ? "bg-primary" : "bg-muted",
      )}
    >
      <span
        className={cn(
          "block size-4 rounded-full bg-background shadow transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

/**
 * A checkbox that belongs to this app's palette instead of to the browser's.
 *
 * `<input type="checkbox">` is unstyleable past a point and renders differently in every
 * engine, which is what made the bank's selection column look pasted in. This is a plain
 * button carrying the ARIA role, so it also gets the focus ring, the hover state and the
 * transition every other control here has.
 *
 * `indeterminate` is what a select-all needs: "some, not all" is a third state, and a
 * header box that shows it as unchecked lies about the selection below it.
 */
export function Checkbox({
  checked,
  indeterminate,
  onCheckedChange,
  disabled,
  label,
  className,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onCheckedChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  className?: string;
}) {
  const marked = checked || Boolean(indeterminate);
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? "mixed" : checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onCheckedChange(!checked);
      }}
      className={cn(
        "inline-flex size-4 shrink-0 items-center justify-center rounded-[5px] border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-40",
        marked
          ? "border-primary bg-primary text-primary-foreground"
          : "border-input bg-background hover:border-primary/70 hover:bg-accent",
        className,
      )}
    >
      {indeterminate ? (
        <Minus className="size-3 stroke-[3.5]" />
      ) : checked ? (
        <Check className="size-3 stroke-[3.5]" />
      ) : null}
    </button>
  );
}

export function Alert({
  tone = "info",
  title,
  children,
  className,
  action,
}: {
  tone?: "info" | "warning" | "danger" | "success";
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  const tones = {
    info: "border-[color-mix(in_oklch,var(--info)_35%,transparent)] bg-[color-mix(in_oklch,var(--info)_10%,transparent)]",
    warning:
      "border-[color-mix(in_oklch,var(--warning)_40%,transparent)] bg-[color-mix(in_oklch,var(--warning)_10%,transparent)]",
    danger: "border-destructive/40 bg-destructive/10",
    success:
      "border-[color-mix(in_oklch,var(--success)_35%,transparent)] bg-[color-mix(in_oklch,var(--success)_10%,transparent)]",
  }[tone];

  return (
    <div className={cn("flex items-start gap-3 rounded-lg border p-3 text-sm", tones, className)}>
      <div className="min-w-0 flex-1">
        {title ? <p className="font-medium">{title}</p> : null}
        {children ? <div className="text-muted-foreground [&_p]:mt-1">{children}</div> : null}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border p-10 text-center">
      {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      <p className="text-sm font-medium">{title}</p>
      {children ? <div className="max-w-md text-sm text-muted-foreground">{children}</div> : null}
    </div>
  );
}
