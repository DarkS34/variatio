import { useId } from "react";

import { useT } from "@/lib/i18n";
import { difficultyLevelsOf, typeLabel } from "@/lib/profile";
import { readableValue } from "@/lib/text";
import type { ActivityWeek, ExemplarsProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * «Qué practican»: where in the syllabus the week's exercises fall, then of which type and level.
 *
 * The syllabus is a strip of its units in order, each bar as long as its share, and — where
 * the course's progress is set — a unit not covered in class yet is dashed, as what lies ahead
 * is everywhere else in the application. Levels go in the order of the type's own scale, never
 * sorted by count. Never a statement: what an exercise said is its author's alone. How many
 * there were, and by whom, is said above it («Lo importante») and below it («Quién genera»).
 */
export function ExercisesBlock({
  week,
  profile,
  colours,
}: {
  week: ActivityWeek;
  profile: ExemplarsProfile | null;
  colours: Map<string, string>;
}) {
  const { t } = useT();
  const id = useId();
  const block = week.exercises;
  const top = Math.max(1, ...block.by_unit.map((row) => row.count));

  return (
    <section aria-labelledby={id} className="surface space-y-5 p-5">
      <h3 id={id} className="text-heading">
        {t("activity.practise")}
      </h3>
      {block.count === 0 ? (
        <p className="text-body text-muted-foreground">{t("activity.exercises.none")}</p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <h4 className="text-micro font-condensed uppercase text-muted-foreground">
              {t("activity.byUnit")}
            </h4>
            <ul className="space-y-2">
              {block.by_unit.map((row) => (
                <li key={row.unit} className="flex items-center gap-2.5">
                  <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: colours.get(row.unit) }} />
                  <span
                    className={cn(
                      "w-40 shrink-0 truncate text-small",
                      row.covered === false && "text-muted-foreground",
                    )}
                    title={row.covered === false ? `${row.unit} · ${t("activity.unit.uncovered")}` : row.unit}
                  >
                    {row.unit}
                  </span>
                  <span
                    className={cn(
                      "h-2.5 flex-1 overflow-hidden rounded-[2px]",
                      row.covered === false ? "border border-dashed border-border" : "bg-muted",
                    )}
                  >
                    <span className="block h-full bg-ink" style={{ width: `${(100 * row.count) / top}%` }} />
                  </span>
                  <span className="nums w-8 shrink-0 text-right text-small">{row.count}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <h4 className="text-micro font-condensed uppercase text-muted-foreground">
              {t("activity.byType")}
            </h4>
            <ul className="rows">
              {block.by_type.map((row) => {
                const spec = profile?.item_types[row.type];
                const ladder = difficultyLevelsOf(spec);
                const levels = Object.entries(row.levels).sort(
                  ([a], [b]) => rank(ladder, a) - rank(ladder, b),
                );
                return (
                  <li key={row.type} className="space-y-1.5 py-2.5">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="truncate font-medium" title={row.type}>
                        {typeLabel(profile, row.type, t)}
                      </span>
                      <span className="nums shrink-0 text-small">{row.count}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {levels.map(([level, count]) => (
                        <span key={level} className="flex items-center gap-1.5 rounded-md bg-sunk px-2 py-0.5 text-small">
                          {level ? readableValue(level) : t("activity.level.none")}
                          <span className="nums text-muted-foreground">{count}</span>
                        </span>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}

/** A level's place in its type's scale; one the scale does not name goes last. */
function rank(ladder: string[], level: string): number {
  const at = ladder.indexOf(level);
  return at < 0 ? ladder.length : at;
}
