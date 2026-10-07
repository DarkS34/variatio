import { FileText, MessageSquare } from "lucide-react";
import { useEffect, useRef, type KeyboardEvent } from "react";

import { weekLabel } from "@/lib/activity";
import { useT } from "@/lib/i18n";
import type { ActivityWeekSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * THE HISTORY OF THE CLASS, ONE WEEK PER STOP: the newest on the left, back to the first
 * week anybody did something.
 *
 * Each week carries its two figures — messages to the tutor and exercises — so the course
 * reads at a glance without opening anything, a dot where its digest is written, and an empty
 * week dimmed but kept: a holiday is a gap, not a week that never was. The one open is the
 * sunk tint, never a relief. One tab stop: the arrows move from week to week (Home and End to
 * the ends), and the week moved to is scrolled into sight.
 */
export function WeekStrip({
  weeks,
  current,
  value,
  onChange,
}: {
  weeks: ActivityWeekSummary[];
  current: string;
  value: string;
  onChange: (week: string) => void;
}) {
  const tr = useT();
  const { t } = tr;
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const present = weeks.find((week) => week.week === current) ?? null;

  useEffect(() => {
    buttons.current.get(value)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [value]);

  const move = (event: KeyboardEvent<HTMLElement>, index: number) => {
    const target =
      event.key === "ArrowLeft"
        ? index - 1
        : event.key === "ArrowRight"
          ? index + 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? weeks.length - 1
              : null;
    if (target === null || target < 0 || target >= weeks.length) return;
    event.preventDefault();
    onChange(weeks[target].week);
    buttons.current.get(weeks[target].week)?.focus();
  };

  return (
    <nav aria-label={t("activity.weeks")} className="surface p-2">
      <ul className="thin-scroll flex gap-1 overflow-x-auto">
        {weeks.map((week, index) => {
          const chosen = week.week === value;
          const empty = week.messages === 0 && week.exercises === 0;
          return (
            <li key={week.week} className="shrink-0">
              <button
                ref={(node) => {
                  if (node) buttons.current.set(week.week, node);
                  else buttons.current.delete(week.week);
                }}
                type="button"
                tabIndex={chosen ? 0 : -1}
                aria-current={chosen ? "true" : undefined}
                title={t("activity.week.title", { messages: week.messages, exercises: week.exercises })}
                onClick={() => onChange(week.week)}
                onKeyDown={(event) => move(event, index)}
                className={cn(
                  "flex w-36 flex-col items-start gap-1 rounded-inner px-3 py-2 text-left transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                  chosen ? "bg-sunk" : "hover:bg-accent",
                )}
              >
                <span
                  className={cn(
                    "flex w-full items-center gap-1.5 text-small font-medium",
                    chosen ? "text-foreground" : empty ? "text-muted-foreground" : "text-foreground/85",
                  )}
                >
                  <span className="truncate">{weekLabel(week, present, t)}</span>
                  {week.digest ? (
                    <span className="ml-auto size-1.5 shrink-0 rounded-full bg-ink" title={t("activity.week.digest")}>
                      <span className="sr-only">{t("activity.week.digest")}</span>
                    </span>
                  ) : null}
                </span>
                <span
                  className={cn(
                    "nums flex items-center gap-2 text-small",
                    empty ? "text-muted-foreground/70" : "text-muted-foreground",
                  )}
                  aria-hidden
                >
                  <span className="flex items-center gap-0.5">
                    <MessageSquare className="size-3" />
                    {week.messages}
                  </span>
                  <span className="flex items-center gap-0.5">
                    <FileText className="size-3" />
                    {week.exercises}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
