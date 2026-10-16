import { barFill } from "@/lib/progress";
import { cn } from "@/lib/utils";

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
  // `null` is "todavía no sé cuánto hay" and it is the only thing that may sweep. A max of
  // ZERO is a total that is known and happens to be zero — an empty bank, a graph with no
  // taggable concepts — and drawing it as the sweep made every one of those screens claim
  // to be loading something for ever. `barFill` is where the two are told apart.
  const fill = barFill(value, max);
  const indeterminate = fill === null;
  const pct = fill ?? 0;
  const colour = {
    primary: "bg-ink",
    settled: "bg-settled",
    attention: "bg-attention-fill",
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
 * A single bar answers "how much is left" and nothing else; a build is seven very
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
                fill >= 1 ? "bg-settled" : "bg-ink",
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
