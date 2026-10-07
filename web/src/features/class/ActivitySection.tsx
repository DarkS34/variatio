import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useState } from "react";

import { Label, Select } from "@/components/ui/input";
import { LoadError, Skeleton } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { domainColour } from "@/lib/format";
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
import { Findings } from "./activity/Findings";
import { TutorBlock } from "./activity/TutorBlock";
import { WeekStrip } from "./activity/WeekStrip";
import { WhoWorks } from "./activity/WhoWorks";

/** The line under «Actividad» in the section list: how many students did something this week. */
export function activityDetail(history: ActivityHistory | undefined, tr: Translate): string | null {
  const present = history?.weeks.find((week) => week.week === history.current);
  return present ? tr.plural("class.activity.detail", present.active) : null;
}

/**
 * «Actividad»: what the class does, week by week, for its teachers (decided 2026-10-07).
 *
 * Two scopes — the whole class, or one student, chosen in the header — and one history: the
 * strip of weeks, the newest first, every week with its two figures. The week open answers
 * three questions in this order: where the class gets stuck («Lo importante», then what they
 * ask the tutor), what it practises, and who has stopped working. One student's week is the
 * same blocks with the class's median beside each figure, and the class's digest cut to the
 * themes their messages fall under.
 *
 * What a teacher reads here is counted by code and summed up by the model in paraphrase: never
 * a conversation, never a statement. The digest is written only when a teacher asks for it;
 * the screen follows its job and reads the week again when it ends.
 */
export function ActivitySection({
  student,
  onStudent,
}: {
  student: number | null;
  onStudent: (id: number | null) => void;
}) {
  const tr = useT();
  const { t } = tr;
  const toast = useToast();
  const client = useQueryClient();
  const pickerId = useId();
  const history = useActivityWeeks(student);
  const [picked, setPicked] = useState<string | null>(null);
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
    <SectionHeader title={t("class.activity")} description={t("activity.lead")} action={picker} />
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

  return (
    <>
      {header}
      <WeekStrip weeks={history.data.weeks} current={history.data.current} value={weekKey} onChange={setPicked} />
      {week.isError ? (
        <LoadError title={t("activity.unreadable")} error={week.error} onRetry={() => week.refetch()} />
      ) : !week.data ? (
        <Skeleton className="h-96" />
      ) : (
        <WeekView
          week={week.data}
          tutorInstalled={history.data.tutor}
          colours={colours}
          profile={profile.data?.profile ?? null}
          run={run}
          writing={write.isPending}
          onWrite={writeDigest}
          onStop={() => run?.job && cancel.mutate(run.job.id)}
          onStudent={onStudent}
        />
      )}
    </>
  );
}

/** One week: what matters, what they ask the tutor, what they practise, and who works. */
function WeekView({
  week,
  tutorInstalled,
  colours,
  profile,
  run,
  writing,
  onWrite,
  onStop,
  onStudent,
}: {
  week: ActivityWeek;
  tutorInstalled: boolean;
  colours: Map<string, string>;
  profile: Parameters<typeof ExercisesBlock>[0]["profile"];
  run: Parameters<typeof TutorBlock>[0]["run"];
  writing: boolean;
  onWrite: () => void;
  onStop: () => void;
  onStudent: (id: number | null) => void;
}) {
  // The tutor's block where the tutor is the class's to use, or where it was used this week.
  const tutor = tutorInstalled && week.tutor && (week.tutor_offered || week.tutor.messages > 0);
  return (
    <>
      <Findings findings={week.findings} />
      {tutor ? (
        <TutorBlock week={week} colours={colours} run={run} writing={writing} onWrite={onWrite} onStop={onStop} />
      ) : null}
      <ExercisesBlock week={week} profile={profile} colours={colours} />
      {week.students ? <WhoWorks rows={week.students} start={week.start} onOpen={onStudent} /> : null}
    </>
  );
}
