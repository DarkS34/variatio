import { Check, Loader2, Minus, RefreshCw } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";

import { errorText } from "@/lib/errors";
import { barFill } from "@/lib/progress";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Button } from "./button";

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
  tone?: "primary" | "settled" | "attention" | "danger";
}) {
  // `null` is «todavía no sé cuánto hay» and it is the only thing that may sweep. A max of
  // ZERO is a total that is known and happens to be zero — an empty bank, a graph with no
  // taggable concepts — and drawing it as the sweep made every one of those screens claim
  // to be loading something for ever. `barFill` is where the two are told apart.
  const fill = barFill(value, max);
  const indeterminate = fill === null;
  const pct = fill ?? 0;
  const colour = {
    primary: "bg-primary",
    settled: "bg-settled",
    attention: "bg-attention",
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
 * Three states, one colour each: done, running (which sweeps, because that is the only
 * part still moving) and pending. The fill inside the running segment is the same
 * percentage the plain bar would have shown.
 *
 * This is NOT replaced by the rail: its stretches carry measured weights and its fill is
 * continuous, and at six pixels tall that reads better as a bar than as nodes. What it
 * does adopt is the rail's vocabulary — the same verdigris for what is finished and the
 * same sweep for what is alive, rather than a pulse of its own.
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
            )}
          >
            <div
              className={cn(
                "relative h-full overflow-hidden rounded-full transition-[width] duration-500 ease-out",
                fill >= 1 ? "bg-settled" : "bg-primary",
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

/**
 * A switch, and the text beside it is part of it.
 *
 * THE LABEL IS A CHILD, NOT A STRING PROPERTY, and that is what the callers were missing.
 * This used to be a bare `<button aria-label={label}>` with no children, so every screen
 * wrote the words a second time in a `<span>` next to it — and that span was not a
 * `<label>`, so it did nothing. Measured before the fix: clicking «Restringir a un
 * currículo» left `aria-checked` at `false`, and the accessible name was announced twice
 * because the visible text repeated the `aria-label` verbatim.
 *
 * With `children` the whole row is the target — 36×20 px becomes the width of the
 * sentence — and the name comes from the text itself, so nothing is said twice. `label`
 * survives for the switches that genuinely have no visible text beside them (a table
 * row's own control), and is ignored when children are given.
 */
export function Switch({
  checked,
  onCheckedChange,
  disabled,
  label,
  children,
  className,
}: {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  children?: ReactNode;
  className?: string;
}) {
  const control = (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      // Only when there is no visible text: with children the `<label>` names it, and a
      // second name here is what the screen reader read twice.
      aria-label={children ? undefined : label}
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

  if (!children) return control;

  return (
    <label
      className={cn(
        "inline-flex cursor-pointer items-center gap-2",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      {control}
      <span className="min-w-0">{children}</span>
    </label>
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
        "relative inline-flex size-4 shrink-0 items-center justify-center rounded-[5px] border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-40",
        // The same 24 px target the (i) gets, and for the same reason: the bank draws 41
        // of these in a column sized to the box, so growing the box would re-space every
        // row of a forty-row table. The pseudo-element is only hit testing.
        "before:absolute before:-inset-1 before:content-['']",
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

export function EmptyState({
  icon,
  title,
  action,
  children,
}: {
  icon?: ReactNode;
  title: string;
  /** What to do so that it stops being empty. An empty screen with no action is a hole;
   *  with one it is where the work starts. Optional on purpose — some holes genuinely have
   *  no action, a search with no results being the obvious one, and forcing a button there
   *  would mean inventing one. */
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border p-12 text-center">
      {icon ? <div className="text-muted-foreground [&_svg]:size-8">{icon}</div> : null}
      <p className="font-display font-expanded text-title">{title}</p>
      {children ? <div className="max-w-md text-muted-foreground">{children}</div> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}

/**
 * A READ THAT FAILED SAYS SO. NO SCREEN MAY RENDER NOTHING INSTEAD.
 *
 * The rule is the study panel's, learned from a route-ordering bug that turned into a card
 * with a heading and no body — «esta función no existe» rather than «esto falló». It was
 * fixed there and nowhere else: with `/api/kg` down, the graph screen still drew its header,
 * its APROBADO badge and «Grafo listo para etiquetar» over an empty page, which is worse
 * than silence — it asserts that the stage is fine while showing none of it. Measured in a
 * browser with the request cut; `/admin` did the same.
 *
 * The retry is part of it: a failed read is very often a blip, and the alternative on offer
 * was reloading the whole application.
 */
export function LoadError({
  title,
  error,
  onRetry,
  className,
}: {
  title: string;
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const { t } = useT();
  return (
    <Alert
      tone="danger"
      title={title}
      className={className}
      action={
        onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw />
            {t("common.retry")}
          </Button>
        ) : undefined
      }
    >
      <p>{errorText(error, t)}</p>
    </Alert>
  );
}
