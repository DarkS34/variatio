import { ChevronRight } from "lucide-react";
import { useId } from "react";

import { Badge } from "@/components/ui/badge";
import { addDays, intensity } from "@/lib/activity";
import { weekdayInitial } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { ActivityStudentRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/** What a page of the activity counts: the exercises generated, or the messages to the tutor. */
export type Measure = "exercises" | "messages";

const WORDS = {
  exercises: { title: "activity.who.exercises", lead: "activity.who.exercisesLead", count: "activity.exercisesN" },
  messages: { title: "activity.who.tutor", lead: "activity.who.tutorLead", count: "activity.messages" },
} as const;

/**
 * «Quién genera» or «Quién usa el tutor»: one row per student of the class, whoever did least
 * of what the page counts first, with the seven days of the week as squares — hollow on a day
 * they did none of it, inked by how much they did. A row opens that student's week.
 */
export function WhoWorks({
  rows,
  start,
  measure,
  onOpen,
}: {
  rows: ActivityStudentRow[];
  start: string;
  measure: Measure;
  onOpen: (id: number) => void;
}) {
  const { t, plural } = useT();
  const id = useId();
  const words = WORDS[measure];
  // An older API sends the days summed; read them as they come.
  const daysOf = (row: ActivityStudentRow) =>
    (measure === "messages" ? row.message_days : row.exercise_days) ?? row.days;
  const sorted = [...rows].sort((a, b) => a[measure] - b[measure] || a.name.localeCompare(b.name));
  const top = Math.max(1, ...sorted.flatMap(daysOf));
  const days = Array.from({ length: 7 }, (_, index) => addDays(start, index));

  return (
    <section aria-labelledby={id} className="surface space-y-4 p-5">
      <div className="space-y-1">
        <h3 id={id} className="text-heading">
          {t(words.title)}
        </h3>
        <p className="text-small text-muted-foreground">{t(words.lead)}</p>
      </div>
      <ul className="rows rows-flush">
        {sorted.map((row) => (
          <li key={row.id}>
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
                {daysOf(row).map((count, index) => (
                  <span key={index} className="flex flex-col items-center gap-0.5">
                    <span
                      className={cn("size-3.5 rounded-[3px]", count === 0 && "border border-border")}
                      style={count > 0 ? { background: "var(--ink)", opacity: intensity(count, top) } : undefined}
                    />
                    <span className="text-micro text-muted-foreground">{weekdayInitial(days[index])}</span>
                  </span>
                ))}
              </span>
              <span className="nums w-28 shrink-0 text-right text-small text-muted-foreground">
                {plural(words.count, row[measure])}
              </span>
              <ChevronRight className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
