import { StatusMark } from "@/components/ui/status";
import { Link } from "@/lib/router";
import { STATUS, statusKey } from "@/lib/status";
import type { ArtifactStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface RailStop {
  key: string;
  label: string;
  status: ArtifactStatus;
  blocked?: boolean;
  /** How much of the width this stretch takes. Defaults to 1; only a weighted plan uses
   *  anything else. */
  weight?: number;
  href?: string;
  active?: boolean;
}

// The application's visual signature, and the condition for using it is strict: ONLY where
// the content really is a sequence with dependencies. That is what separates it from a
// decorative "01 / 02 / 03", and it is why it does not appear in the bank's item list, in
// the administration tables, or in the tabs of «Mi perfil» — none of those three is one.
//
// The stretch says whether the dependency is satisfied: solid once what precedes it is
// settled, dotted once it is downstream and not reachable yet. It is the same drawing as
// the graph's curriculum view, at another scale.
export function Rail({
  stops,
  size = "md",
  showLabels = true,
  className,
}: {
  stops: RailStop[];
  size?: "sm" | "md";
  showLabels?: boolean;
  className?: string;
}) {
  const solid = "bg-[color-mix(in_oklch,var(--settled)_55%,transparent)]";
  const dotted = "bg-[repeating-linear-gradient(to_right,var(--border)_0_3px,transparent_3px_6px)]";

  // A stretch is solid when what sits BEHIND it is resolved. Looking at the next node
  // instead would say something else: that a pending step breaks the line leading up to
  // it, when what the line reports is that you can get there.
  const reachedFrom = (index: number) => {
    const previous = stops[index - 1];
    return Boolean(
      previous && !previous.blocked && (previous.status === "approved" || previous.status === "building"),
    );
  };

  return (
    <ol className={cn("flex w-full items-start", className)}>
      {stops.map((stop, index) => {
        const meta = STATUS[statusKey(stop.status, Boolean(stop.blocked))];
        const body = (
          <span className="flex flex-col items-center gap-1">
            <StatusMark status={stop.status} blocked={stop.blocked} size={size} />
            {showLabels ? (
              <span
                className={cn(
                  "whitespace-nowrap text-micro font-condensed uppercase transition-colors",
                  stop.active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {stop.label}
              </span>
            ) : null}
          </span>
        );

        return (
          <li
            key={stop.key}
            style={{ flexGrow: stop.weight ?? 1 }}
            className="flex min-w-0 basis-0 items-start"
          >
            {index > 0 ? (
              <span
                aria-hidden
                className={cn("mt-[5px] h-px min-w-3 flex-1", reachedFrom(index) ? solid : dotted)}
              />
            ) : null}

            {stop.href ? (
              <Link to={stop.href} title={`${stop.label} — ${meta.label}`}>
                {body}
              </Link>
            ) : (
              <span title={`${stop.label} — ${meta.label}`}>{body}</span>
            )}

            {index < stops.length - 1 ? (
              <span
                aria-hidden
                className={cn("mt-[5px] h-px min-w-3 flex-1", reachedFrom(index + 1) ? solid : dotted)}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
