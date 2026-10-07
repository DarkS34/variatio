import { PenLine, RefreshCw, Square } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { Segments } from "@/features/admin/charts";
import { kindShares } from "@/lib/activity";
import { dateTime } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { isLive, isQueued } from "@/lib/queue";
import type { ActivityDigest, ActivityTutor, ActivityWeek } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { RunView } from "@/state/runStore";

/** The fewest messages about the subject a week needs before its digest is offered. */
export const DIGEST_MIN_MESSAGES = 10;

/**
 * «Qué preguntan»: the week's digest — the themes the class keeps asking about, unit by unit in
 * the syllabus' order — or, before there is one, the concepts most asked about, counted by code.
 *
 * The digest is the teacher's to ask for and never written on its own: one button that says
 * what it will do («Escribir», «Actualizar» on the open week, a quiet «Escribir otra vez» on a
 * closed one), the state of the job while it runs (queued behind the class's own turns, then
 * writing, with «Detener»), and the date it was written with how many messages arrived since.
 */
export function TutorAsks({
  week,
  colours,
  run,
  writing,
  onWrite,
  onStop,
}: {
  week: ActivityWeek;
  colours: Map<string, string>;
  run: RunView | null;
  writing: boolean;
  onWrite: () => void;
  onStop: () => void;
}) {
  const { t } = useT();
  const id = useId();
  const tutor = week.tutor as ActivityTutor;
  return (
    <section aria-labelledby={id} className="surface space-y-4 p-5">
      <h3 id={id} className="text-heading">
        {t("activity.ask")}
      </h3>
      {tutor.messages === 0 ? (
        <p className="text-body text-muted-foreground">{t("activity.tutor.none")}</p>
      ) : (
        <DigestPanel week={week} colours={colours} run={run} writing={writing} onWrite={onWrite} onStop={onStop} />
      )}
    </section>
  );
}

/**
 * «Cómo preguntan»: what the week's messages ask for — theory, help, a review, the solution —
 * and the prerequisites the tutor sent them back to. Drawn only on a week with messages.
 */
export function TutorWays({ week }: { week: ActivityWeek }) {
  const { t, plural } = useT();
  const id = useId();
  const tutor = week.tutor as ActivityTutor;
  const student = week.scope === "student";
  return (
    <section aria-labelledby={id} className="surface space-y-4 p-5">
      <h3 id={id} className="text-heading">
        {t("activity.ways")}
      </h3>
      <div className={cn("grid gap-6", tutor.sent_back.length > 0 && "md:grid-cols-2")}>
        <div className="space-y-3">
          <h4 className="text-micro font-condensed uppercase text-muted-foreground">{t("activity.kinds")}</h4>
          <Segments
            segments={kindShares(tutor.by_kind).map((share) => ({
              key: share.key,
              label: t(share.label),
              value: share.value,
            }))}
          />
        </div>
        {tutor.sent_back.length > 0 ? (
          <div className="space-y-2">
            <h4 className="text-micro font-condensed uppercase text-muted-foreground">{t("activity.sentBack")}</h4>
            <ul className="rows">
              {tutor.sent_back.map((row) => (
                <li key={`${row.concept}-${row.prerequisite}`} className="flex items-baseline gap-2 py-1.5">
                  <span className="min-w-0 flex-1 text-small">
                    <span className="font-medium">«{row.prerequisite}»</span>{" "}
                    <span className="text-muted-foreground">
                      {t("activity.sentBack.from", { concept: row.concept })}
                    </span>
                  </span>
                  <span className="nums shrink-0 text-small text-muted-foreground">
                    {student ? plural("activity.messages", row.times) : plural("activity.students", row.students)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}

/** The digest of the week, its state and its one button; the most asked concepts until it exists. */
function DigestPanel({
  week,
  colours,
  run,
  writing,
  onWrite,
  onStop,
}: {
  week: ActivityWeek;
  colours: Map<string, string>;
  run: RunView | null;
  writing: boolean;
  onWrite: () => void;
  onStop: () => void;
}) {
  const { t, plural } = useT();
  const digest = week.digest;
  const live = isLive(run?.job);
  const queued = live && isQueued(run?.job ?? null);
  const failed = run?.job?.status === "failed";
  const onSubject = Object.entries(week.tutor?.by_kind ?? {})
    .filter(([kind]) => ["theory", "exercise", "attempt", "solution"].includes(kind))
    .reduce((total, [, n]) => total + n, 0);

  // What the button does here: write, update the open week, or, quietly, write a closed one again.
  const action = !digest
    ? { label: t("activity.digest.write"), icon: <PenLine />, variant: "outline" as const }
    : week.closed
      ? { label: t("activity.digest.again"), icon: <RefreshCw />, variant: "ghost" as const }
      : { label: t("activity.digest.update"), icon: <RefreshCw />, variant: "outline" as const };
  // A student's reading shows the class's digest cut to them; it is written from the class.
  const offered = week.scope === "class" && week.digest_ready && !live && !week.digest_running;

  const state = live ? (
    <span className="flex items-center gap-2">
      {queued ? null : <Spinner />}
      {t(queued ? "activity.digest.queued" : "activity.digest.running")}
    </span>
  ) : week.digest_running ? (
    t("activity.digest.other")
  ) : failed ? (
    <span className="text-destructive">{t("activity.digest.failed")}</span>
  ) : digest ? (
    [
      digest.written_at ? t("activity.digest.written", { date: dateTime(digest.written_at) }) : null,
      !week.closed && digest.new_since > 0 ? plural("activity.digest.new", digest.new_since) : null,
    ]
      .filter(Boolean)
      .join(" · ")
  ) : week.digest_ready ? (
    t("activity.digest.none")
  ) : (
    t("activity.digest.notEnough", { n: onSubject, min: DIGEST_MIN_MESSAGES })
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-small text-muted-foreground">{state}</p>
        {live ? (
          <Button size="sm" variant="ghost" onClick={onStop}>
            <Square />
            {t("activity.digest.stop")}
          </Button>
        ) : offered ? (
          <Button size="sm" variant={action.variant} disabled={writing} onClick={onWrite}>
            {writing ? <Spinner /> : action.icon}
            {action.label}
          </Button>
        ) : null}
      </div>
      {digest ? (
        <Themes digest={digest} colours={colours} student={week.scope === "student"} />
      ) : (
        <MostAsked week={week} colours={colours} />
      )}
    </div>
  );
}

/** The digest's themes, unit by unit and concept by concept, each with whom it covers. */
function Themes({
  digest,
  colours,
  student,
}: {
  digest: ActivityDigest;
  colours: Map<string, string>;
  student: boolean;
}) {
  const { t, plural } = useT();
  if (digest.concepts.length === 0) {
    return <p className="text-body text-muted-foreground">{t("activity.digest.empty")}</p>;
  }
  const units: { unit: string | null; concepts: ActivityDigest["concepts"] }[] = [];
  for (const entry of digest.concepts) {
    const last = units[units.length - 1];
    if (last && last.unit === entry.unit) last.concepts.push(entry);
    else units.push({ unit: entry.unit, concepts: [entry] });
  }
  return (
    <div className="space-y-5">
      {units.map((group, index) => (
        <div key={`${group.unit}-${index}`} className="space-y-3">
          {group.unit ? (
            <p className="flex items-center gap-2 text-micro font-condensed uppercase text-muted-foreground">
              <span aria-hidden className="size-2 rounded-full" style={{ background: colours.get(group.unit) }} />
              {group.unit}
            </p>
          ) : null}
          {group.concepts.map((entry) => (
            <div key={entry.concept} className="space-y-1.5">
              <p className="font-medium">«{entry.concept}»</p>
              <ul className="rows">
                {entry.themes.map((theme) => (
                  <li key={theme.text} className="flex items-baseline justify-between gap-4 py-2">
                    <span className="text-body">{theme.text}</span>
                    <span className="nums shrink-0 text-small text-muted-foreground">
                      {student && theme.mine !== undefined
                        ? plural("activity.digest.mine", theme.mine)
                        : `${plural("activity.students", theme.students)} · ${plural("activity.messages", theme.messages)}`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ))}
      <p className="text-small text-muted-foreground">{t("activity.digest.note")}</p>
    </div>
  );
}

/** The concepts most asked about this week, counted by code, before any digest is written. */
function MostAsked({ week, colours }: { week: ActivityWeek; colours: Map<string, string> }) {
  const { t, plural } = useT();
  const rows = [...(week.tutor?.by_concept ?? [])]
    .sort((a, b) => b.students - a.students || b.messages - a.messages)
    .slice(0, 6);
  if (rows.length === 0) return null;
  const top = Math.max(...rows.map((row) => row.messages));
  return (
    <div className="space-y-2">
      <h4 className="text-micro font-condensed uppercase text-muted-foreground">{t("activity.asked")}</h4>
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li key={row.concept} className="flex items-center gap-3">
            <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: colours.get(row.unit ?? "") }} />
            <span className="w-48 shrink-0 truncate text-small" title={row.concept}>
              {row.concept}
            </span>
            <span className="h-2.5 flex-1 overflow-hidden rounded-[2px] bg-muted">
              <span className="block h-full bg-ink" style={{ width: `${(100 * row.messages) / top}%` }} />
            </span>
            <span className="nums w-40 shrink-0 text-right text-small text-muted-foreground">
              {week.scope === "student"
                ? plural("activity.messages", row.messages)
                : `${plural("activity.students", row.students)} · ${plural("activity.messages", row.messages)}`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
