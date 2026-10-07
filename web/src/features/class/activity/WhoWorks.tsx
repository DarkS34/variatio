import { ChevronRight } from "lucide-react";
import { useId } from "react";

import { Badge } from "@/components/ui/badge";
import { addDays, intensity } from "@/lib/activity";
import { weekdayInitial } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { ActivityStudentRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * «Quién trabaja»: one row per student of the class, whoever did least first, with the seven
 * days of the week as squares — hollow on a day they did nothing, inked by how much they did.
 * A row opens that student's week.
 */
export function WhoWorks({
  rows,
  start,
  onOpen,
}: {
  rows: ActivityStudentRow[];
  start: string;
  onOpen: (id: number) => void;
}) {
  const { t, plural } = useT();
  const id = useId();
  const top = Math.max(1, ...rows.flatMap((row) => row.days));
  const days = Array.from({ length: 7 }, (_, index) => addDays(start, index));

  return (
    <section aria-labelledby={id} className="surface space-y-3 p-5">
      <div className="space-y-0.5">
        <h3 id={id} className="text-heading">
          {t("activity.who")}
        </h3>
        <p className="text-small text-muted-foreground">{t("activity.who.lead")}</p>
      </div>
      <ul className="rows">
        {rows.map((row) => (
          <li key={row.id} className="py-0">
            <button
              type="button"
              aria-label={t("activity.who.open", { name: row.name })}
              onClick={() => onOpen(row.id)}
              className="group -mx-2 flex w-[calc(100%+1rem)] items-center gap-3 rounded-inner px-2 py-2.5 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
            >
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className={cn("truncate font-medium", row.disabled && "text-muted-foreground")}>
                    {row.name}
                  </span>
                  {row.disabled ? <Badge variant="outline">{t("activity.paused")}</Badge> : null}
                </span>
                <span className="block truncate font-mono text-small text-muted-foreground">
                  {row.username}
                </span>
              </span>
              <span className="hidden items-center gap-1 sm:flex" aria-hidden>
                {row.days.map((count, index) => (
                  <span key={index} className="flex flex-col items-center gap-0.5">
                    <span
                      className={cn("size-3.5 rounded-[3px]", count === 0 && "border border-border")}
                      style={count > 0 ? { background: "var(--ink)", opacity: intensity(count, top) } : undefined}
                    />
                    <span className="text-micro text-muted-foreground">{weekdayInitial(days[index])}</span>
                  </span>
                ))}
              </span>
              <span className="nums w-44 shrink-0 text-right text-small text-muted-foreground">
                {plural("activity.messages", row.messages)} · {plural("activity.exercisesN", row.exercises)}
              </span>
              <ChevronRight className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
