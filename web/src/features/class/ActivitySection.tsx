import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useMemo } from "react";

import { Label, Select } from "@/components/ui/input";
import { LoadError, Skeleton } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { findingsIn, weekBefore } from "@/lib/activity";
import { domainColour, number } from "@/lib/format";
import { useT, type Translate } from "@/lib/i18n";
import { isLive } from "@/lib/queue";
import type { ActivityHistory, ActivityWeek } from "@/lib/types";
import {
  keys,
  useActivityWeek,
  useActivityWeeks,
  useCancelJob,
  useOwnJobRun,
  useProfile,
  useWriteDigest,
} from "@/state/queries";

import { ExercisesBlock } from "./activity/ExercisesBlock";
import { Findings, type WeekFigure } from "./activity/Findings";
import { TutorAsks, TutorWays } from "./activity/TutorBlock";
import { WeekStrip } from "./activity/WeekStrip";
import { WhoWorks, type Measure } from "./activity/WhoWorks";

/** The line under «Ejercicios generados» or «Tutor socrático» in the section list: this week's count. */
export function activityDetail(
  history: ActivityHistory | undefined,
  view: ActivityView,
  tr: Translate,
): string | null {
  const present = history?.weeks.find((week) => week.week === history.current);
  if (!present) return null;
  return view === "tutor"
    ? tr.plural("class.activity.tutorDetail", present.messages)
    : tr.plural("class.activity.exercisesDetail", present.exercises);
}

/** The two pages of «Actividad», one for each thing a student uses: the exercises and the tutor. */
export type ActivityView = "exercises" | "tutor";

const TITLE_KEYS = {
  exercises: "class.activity.exercises",
  tutor: "class.activity.tutor",
} as const;

const LEAD_KEYS = {
  exercises: "activity.exercises.lead",
  tutor: "activity.tutor.lead",
} as const;

const MEASURE: Record<ActivityView, Measure> = { exercises: "exercises", tutor: "messages" };

/**
 * «Actividad»: what the class does, week by week, for its teachers (decided 2026-10-07).
 *
 * Two pages, one for each thing a student uses (user's request, 2026-10-07: a page of the week
 * in general read as neither): «Ejercicios generados» and «Tutor socrático». Each answers the
 * same three questions in the same order — how the week went («Lo importante»: three key
 * figures, then the server's findings of that page), what it was about («Qué practican»;
 * «Qué preguntan» and «Cómo preguntan»), and who did it («Quién genera», «Quién usa el
 * tutor», the least first). Both carry the scope, the whole class or one student, and the
 * strip of weeks counting the page's own figure; the screen holds the scope and the week, so
 * moving between the pages keeps them. One student's week is the same blocks with the class's
 * median among its figures, and the class's digest cut to the themes their messages fall under.
 *
 * What a teacher reads here is counted by code and summed up by the model in paraphrase: never
 * a conversation, never a statement. The digest is written only when a teacher asks for it;
 * the screen follows its job and reads the week again when it ends.
 */
export function ActivitySection({
  view,
  student,
  onStudent,
  week: picked,
  onWeek,
}: {
  view: ActivityView;
  student: number | null;
  onStudent: (id: number | null) => void;
  week: string | null;
  onWeek: (week: string) => void;
}) {
  const tr = useT();
  const { t } = tr;
  const toast = useToast();
  const client = useQueryClient();
  const pickerId = useId();
  const history = useActivityWeeks(student);
  const weekKey = picked ?? history.data?.current ?? null;
  const week = useActivityWeek(weekKey, student);
  const profile = useProfile();
  const write = useWriteDigest();
  const cancel = useCancelJob();
  const run = useOwnJobRun("activity_digest", (candidate) => candidate.job?.params?.week === weekKey);
  const live = isLive(run?.job);

  // The digest's job ending is the moment to read the week again: its themes have landed.
  useEffect(() => {
    if (run?.job && !live) client.invalidateQueries({ queryKey: keys.activity });
  }, [live, run?.job?.status, client, run?.job]);

  const colours = useMemo(() => {
    const units = week.data?.exercises.by_unit.map((row) => row.unit) ?? [];
    return new Map(units.map((unit, index) => [unit, domainColour(index, units.length)]));
  }, [week.data]);

  const writeDigest = () =>
    weekKey &&
    write.mutate(weekKey, {
      onSuccess: () => toast({ title: t("activity.digest.started") }),
      onError: (error: Error) =>
        toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
    });

  const students = history.data?.students ?? [];
  const picker = (
    <div className="flex items-center gap-2">
      <Label htmlFor={pickerId} className="sr-only">
        {t("activity.scope.label")}
      </Label>
      <Select
        id={pickerId}
        value={student === null ? "" : String(student)}
        className="w-full sm:w-64"
        onChange={(event) => onStudent(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">{t("activity.scope.class")}</option>
        {students.map((row) => (
          <option key={row.id} value={row.id}>
            {row.disabled ? t("activity.scope.paused", { name: row.name }) : row.name}
          </option>
        ))}
      </Select>
    </div>
  );

  const header = (
    <SectionHeader title={t(TITLE_KEYS[view])} description={t(LEAD_KEYS[view])} action={picker} />
  );

  if (history.isError) {
    return (
      <>
        {header}
        <LoadError title={t("activity.unreadable")} error={history.error} onRetry={() => history.refetch()} />
      </>
    );
  }
  if (!history.data || !weekKey) {
    return (
      <>
        {header}
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </>
    );
  }

  const data = week.data;
  const measure = MEASURE[view];
  return (
    <>
      {header}
      <WeekStrip
        weeks={history.data.weeks}
        current={history.data.current}
        value={weekKey}
        measure={measure}
        onChange={onWeek}
      />
      {week.isError ? (
        <LoadError title={t("activity.unreadable")} error={week.error} onRetry={() => week.refetch()} />
      ) : !data ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <Findings
            findings={findingsIn(data.findings, view === "tutor" ? "tutor" : "exercises").filter(
              // Nobody writing to a tutor the class may not use is no news.
              (finding) => view !== "tutor" || data.tutor_offered !== false || finding.kind !== "idle",
            )}
            figures={figuresOf(view, data, history.data, tr)}
          />
          {view === "exercises" ? (
            <ExercisesBlock week={data} profile={profile.data?.profile ?? null} colours={colours} />
          ) : data.tutor ? (
            <>
              <TutorAsks
                week={data}
                colours={colours}
                run={run}
                writing={write.isPending}
                onWrite={writeDigest}
                onStop={() => run?.job && cancel.mutate(run.job.id)}
              />
              {data.tutor.messages > 0 ? <TutorWays week={data} /> : null}
            </>
          ) : null}
          {data.students ? (
            <WhoWorks rows={data.students} start={data.start} measure={measure} onOpen={onStudent} />
          ) : null}
        </>
      )}
    </>
  );
}

/**
 * The three key figures of a page's week: how much, by how many (or, for one student, the
 * class's median), and the one that says most of how it was used — the exercises taken to the
 * tutor, the messages asking for the solution.
 */
function figuresOf(view: ActivityView, week: ActivityWeek, history: ActivityHistory, tr: Translate): WeekFigure[] {
  const { t, plural } = tr;
  const before = weekBefore(history.weeks, week.week);
  const trend = (now: number, then: number | undefined) => {
    if (then === undefined) return null;
    const diff = now - then;
    return diff === 0 ? t("activity.fig.same") : plural(diff > 0 ? "activity.fig.up" : "activity.fig.down", Math.abs(diff));
  };
  const student = week.scope === "student";
  const figures: WeekFigure[] = [];
  if (view === "exercises") {
    const block = week.exercises;
    figures.push({
      key: "count",
      label: t("activity.fig.exercises"),
      value: number(block.count),
      note: trend(block.count, before?.exercises),
    });
    figures.push(
      student
        ? {
            key: "median",
            label: t("activity.fig.median"),
            value: number(week.median?.exercises ?? 0),
            note: t("activity.fig.medianNote"),
          }
        : {
            key: "who",
            label: t("activity.fig.generating"),
            value: number(block.students),
            note: t("activity.fig.ofClass", { n: week.class_size }),
          },
    );
    if (history.tutor) {
      figures.push({
        key: "tutor",
        label: t("activity.fig.toTutor"),
        value: number(block.to_tutor),
        note: t("activity.fig.toTutorNote"),
      });
    }
    return figures;
  }
  const tutor = week.tutor;
  if (!tutor) return figures;
  const solution = tutor.by_kind.solution ?? 0;
  figures.push({
    key: "count",
    label: t("activity.fig.messages"),
    value: number(tutor.messages),
    note: trend(tutor.messages, before?.messages),
  });
  figures.push(
    student
      ? {
          key: "median",
          label: t("activity.fig.median"),
          value: number(week.median?.messages ?? 0),
          note: t("activity.fig.medianNote"),
        }
      : {
          key: "who",
          label: t("activity.fig.asking"),
          value: number(tutor.students),
          note: t("activity.fig.ofClass", { n: week.class_size }),
        },
  );
  figures.push({
    key: "solution",
    label: t("activity.fig.solution"),
    value: number(solution),
    note: tutor.messages > 0 ? t("activity.fig.share", { pct: Math.round((100 * solution) / tutor.messages) }) : null,
  });
  return figures;
}
