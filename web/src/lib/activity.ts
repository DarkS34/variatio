import { dayMonth, number } from "@/lib/format";
import type { Key, Translate } from "@/lib/i18n";
import type { ActivityFinding, ActivityWeekSummary } from "@/lib/types";

/**
 * What the class activity screen decides without React: how a week is named on the strip,
 * how the replies' kinds are grouped, and how a finding is said.
 *
 * The server counts and types each finding (`server/activity.py`); the words are the
 * reader's language's, so they are composed here from the figures it sends.
 */

/** Add days to a `YYYY-MM-DD` date. */
export function addDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

/** How the strip names a week: this one, the one before, or its Monday to its Sunday. */
export function weekLabel(
  week: Pick<ActivityWeekSummary, "week" | "start">,
  current: { week: string; start: string } | null,
  t: Translate["t"],
): string {
  if (current && week.week === current.week) return t("activity.week.current");
  if (current && week.start === addDays(current.start, -7)) return t("activity.week.previous");
  return t("activity.week.range", { from: dayMonth(week.start), to: dayMonth(addDays(week.start, 6)) });
}

/** The kinds of reply that say what the class asks for, in the order of a student's way in. */
export const ASKING_KINDS = ["theory", "exercise", "attempt", "solution"] as const;

const KIND_KEYS: Record<(typeof ASKING_KINDS)[number] | "other", Key> = {
  theory: "activity.kind.theory",
  exercise: "activity.kind.exercise",
  attempt: "activity.kind.attempt",
  solution: "activity.kind.solution",
  other: "activity.kind.other",
};

/**
 * The replies' kinds as the shares the screen draws: the four that work on the subject, then
 * everything else (greetings, administrative questions, refusals) as one «other».
 */
export function kindShares(byKind: Record<string, number>): { key: string; label: Key; value: number }[] {
  const asking = new Set<string>(ASKING_KINDS);
  const other = Object.entries(byKind)
    .filter(([kind]) => !asking.has(kind))
    .reduce((total, [, value]) => total + value, 0);
  return [...ASKING_KINDS, "other" as const]
    .map((kind) => ({
      key: kind,
      label: KIND_KEYS[kind],
      value: kind === "other" ? other : (byKind[kind] ?? 0),
    }))
    .filter((share) => share.value > 0);
}

/** A finding as the screen says it: the figure it leads with, its sentence, and whether to act. */
export interface FindingView {
  figure: string;
  text: string;
  /** The one the teacher should act on: drawn in `--attention`, never more than one. */
  act: boolean;
}

// The findings a teacher can act on, in the order the server ranks them.
const ACTIONABLE = new Set<ActivityFinding["kind"]>(["asked", "solutions", "unpractised", "idle"]);

/** Word a week's findings; the first one a teacher can act on carries the attention. */
export function sayFindings(findings: ActivityFinding[], tr: Translate): FindingView[] {
  let acted = false;
  return findings.map((finding) => {
    const view = sayFinding(finding, tr);
    const act = !acted && ACTIONABLE.has(finding.kind);
    acted ||= act;
    return { ...view, act };
  });
}

function sayFinding(finding: ActivityFinding, { t, plural }: Translate): Omit<FindingView, "act"> {
  const n = (value: number) => number(value);
  switch (finding.kind) {
    case "asked":
      return {
        figure: n(finding.students),
        text:
          plural("activity.finding.asked", finding.students, { of: finding.of, concept: finding.concept }) +
          (finding.prerequisite && finding.sent_back > 0
            ? " " +
              plural("activity.finding.askedBack", finding.sent_back, { prerequisite: finding.prerequisite })
            : ""),
      };
    case "solutions":
      return {
        figure: n(finding.solution),
        text: t("activity.finding.solutions", {
          solution: finding.solution,
          messages: finding.messages,
          concept: finding.concept,
        }),
      };
    case "unpractised":
      return {
        figure: n(finding.units.length + finding.more),
        text: plural("activity.finding.unpractised", finding.units.length + finding.more, {
          units: finding.units.map((unit) => t("activity.unitName", { unit })).join(", "),
        }),
      };
    case "idle":
      return {
        figure: n(finding.students),
        text: plural(finding.open ? "activity.finding.idleOpen" : "activity.finding.idle", finding.students, {
          of: finding.of,
        }),
      };
    case "trend": {
      const diff = finding.active - finding.previous;
      return {
        figure: n(finding.active),
        text: plural(diff < 0 ? "activity.finding.trendDown" : "activity.finding.trendUp", finding.active, {
          diff: Math.abs(diff),
        }),
      };
    }
    case "quiet":
      return {
        figure: "0",
        text: t(finding.open ? "activity.finding.quietOpen" : "activity.finding.quiet"),
      };
    case "topic":
      return {
        figure: n(finding.messages),
        text: plural("activity.finding.topic", finding.messages, { concept: finding.concept }),
      };
    case "reviewed":
      return {
        figure: n(finding.times),
        text: plural("activity.finding.reviewed", finding.times, { prerequisite: finding.prerequisite }),
      };
    case "practised":
      return {
        figure: n(finding.exercises),
        text: plural("activity.finding.practised", finding.exercises, { unit: finding.unit }),
      };
  }
}

/** How strongly a cell is painted: none for zero, then a floor so one is visible at all. */
export function intensity(count: number, max: number): number {
  if (count <= 0 || max <= 0) return 0;
  return 0.18 + 0.82 * (count / max);
}
