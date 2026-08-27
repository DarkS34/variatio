import { Ban, FileText, Hammer, Hourglass, PenLine, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, PhaseBar, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import type { RawSlot } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import { useCancelJob, useEngineOffline } from "@/state/queries";

import { DocumentDialog } from "./DocumentDialog";
import { busyDocument, documentLoop, innerLoop, loopLabel } from "./progress";
import {
  useStartTranscription,
  useTranscribePhases,
  useTranscribeRun,
  useTranscribing,
  useTranscription,
} from "./queries";
import type { DocumentState } from "./types";
import { useT, type Key, type Translate } from "@/lib/i18n";

const STATE: Record<
  DocumentState,
  { labelKey: Key; variant: "settled" | "outline" | "attention" }
> = {
  done: { labelKey: "transcribe.state.done", variant: "settled" },
  pending: { labelKey: "transcribe.state.pending", variant: "outline" },
  stale: { labelKey: "transcribe.state.stale", variant: "attention" },
};

function launchLabel(pending: number, stale: number, done: number, t: Translate["t"]): string {
  if (stale > 0 && pending > 0) return t("transcribe.pendingAndStale");
  if (stale > 0) return t("transcribe.staleOnly");
  if (done > 0) return t("transcribe.pendingOnly");
  return t("transcribe.start");
}

function SlotTranscription({ slot }: { slot: RawSlot }) {
  const { t, plural } = useT();
  const hasFiles = slot.files.length > 0;
  const state = useTranscription(slot.kind, hasFiles);
  const run = useTranscribeRun(slot.kind);
  const running = useTranscribing(slot.kind);
  const phases = useTranscribePhases();
  const start = useStartTranscription();
  const cancel = useCancelJob();
  const offline = useEngineOffline();
  const canEdit = useCanEdit();
  const [opened, setOpened] = useState<string | null>(null);

  const data = state.data;
  const todo = (data?.pending ?? 0) + (data?.stale ?? 0);
  const overall = run?.overall ?? null;
  const queued = run?.job?.status === "queued";
  // Two nested loops, drawn as two bars: which document of how many, and how far into that
  // document's pages (or, once they are done, into its seams).
  const docs = documentLoop(run);
  const inner = innerLoop(run);
  // The one document nobody may correct while this runs: the transcriber rewrites its whole
  // directory at the end, so an edit saved into it now would be discarded without a word.
  const busy = busyDocument(run);

  const reason = !canEdit
    ? t("build.readOnly")
    : offline
      ? offline
      : running
        ? t("transcribe.alreadyRunning")
        : start.isPending
          ? t("common.sending")
          : todo === 0
            ? t("transcribe.allDone")
            : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <FileText className="size-4 shrink-0 text-muted-foreground" />
          <CardTitle className="flex-1">{slot.label}</CardTitle>
          {data ? (
            data.stale > 0 ? (
              <Badge variant="attention">{plural("transcribe.staleCount", data.stale)}</Badge>
            ) : data.pending > 0 ? (
              <Badge variant="outline">{plural("transcribe.pendingCount", data.pending)}</Badge>
            ) : (
              <Badge variant="settled">{t("transcribe.upToDate")}</Badge>
            )
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {!hasFiles ? (
          <p className="text-small text-muted-foreground">{t("transcribe.noDocuments")}</p>
        ) : state.isLoading ? (
          <Skeleton className="h-24" />
        ) : !data ? (
          <Alert tone="danger" title={t("transcribe.unreadable")}>
            <p>{t("transcribe.noResponse", { path: `/api/raw/${slot.kind}/transcription` })}</p>
          </Alert>
        ) : (
          <>
            <p className="text-small nums text-muted-foreground">
              {plural("transcribe.documents", data.documents.length)}
              {data.total_pages > 0 ? plural("transcribe.pages", data.total_pages) : ""}
              {t("transcribe.oneCallPerPage")}
            </p>

            <Button
              size="sm"
              variant={data.stale > 0 && data.pending === 0 ? "outline" : "default"}
              disabled={Boolean(reason)}
              title={
                reason ??
                (data.done > 0
                  ? t("transcribe.startHintSome")
                  : t("transcribe.startHintNone"))
              }
              onClick={() => start.mutate(slot.kind)}
            >
              {start.isPending ? (
                <Spinner />
              ) : data.stale > 0 ? (
                <RefreshCw />
              ) : (
                <Hammer />
              )}
              {launchLabel(data.pending, data.stale, data.done, t)}
            </Button>

            {running ? (
              <div className="space-y-2 rounded-md border border-border p-2.5">
                <div className="flex items-center gap-2">
                  {queued ? (
                    <Hourglass className="size-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <Spinner className="shrink-0" />
                  )}
                  <span className="min-w-0 flex-1 truncate text-small">
                    {queued
                      ? t("transcribe.queued")
                      : (overall?.label ?? docs?.label ?? t("transcribe.preparing"))}
                  </span>
                  {docs ? (
                    <span className="shrink-0 text-small font-medium nums">
                      {t("transcribe.docCounter", { n: loopLabel(docs) })}
                    </span>
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={cancel.isPending || !run?.job}
                    title={t("transcribe.stopHint")}
                    onClick={() => run?.job && cancel.mutate(run.job.id)}
                  >
                    <Ban />
                    {t("common.stop")}
                  </Button>
                </div>

                {!queued ? (
                  <>
                    {overall && phases.length > 0 ? (
                      <PhaseBar
                        phases={phases}
                        percent={overall.percent}
                        activeKey={overall.key}
                      />
                    ) : (
                      <Progress value={overall?.percent ?? 0} max={100} />
                    )}
                    {overall?.detail ? (
                      <p className="truncate text-small text-muted-foreground">
                        {overall.detail}
                      </p>
                    ) : null}

                    {/* The inner loop, drawn as its own bar: the outer one moves once per
                        document, so on a corpus of long PDFs it would sit still for as long
                        as it takes to read one — which reads as a stall and is not. */}
                    {inner ? (
                      <div className="space-y-1 border-l-2 border-border pl-2.5">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="min-w-0 truncate text-small text-muted-foreground">
                            {inner.detail ?? inner.label}
                          </span>
                          <span className="shrink-0 nums text-small text-muted-foreground">
                            {loopLabel(inner)}
                          </span>
                        </div>
                        <Progress value={inner.current} max={inner.total} />
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}

            {data.documents.length > 0 ? (
              <ul className="divide-y divide-border rounded-md border border-border">
                {data.documents.map((entry) => (
                  <li key={entry.name} className="space-y-0.5 px-2 py-1.5">
                    <div className="flex items-center gap-2 text-small">
                      {busy === entry.name ? <Spinner className="size-3.5 shrink-0" /> : null}
                      <span className="min-w-0 flex-1 truncate" title={entry.name}>
                        {entry.name}
                      </span>
                      {entry.pages > 0 ? (
                        <span className="shrink-0 nums text-muted-foreground">
                          {t("transcribe.pageAbbrev", { n: entry.pages })}
                        </span>
                      ) : null}
                      <Badge
                        variant={
                          busy === entry.name ? "outline" : STATE[entry.state]?.variant ?? "outline"
                        }
                      >
                        {busy === entry.name
                          ? t("transcribe.transcribing")
                          : STATE[entry.state]
                            ? t(STATE[entry.state].labelKey)
                            : entry.state}
                      </Badge>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        aria-label={t("transcribe.reviewPagesOf", { name: entry.name })}
                        title={
                          busy === entry.name
                            ? t("transcribe.beingRewritten")
                            : entry.state === "pending"
                              ? t("transcribe.noPagesYet")
                              : t("transcribe.reviewPages")
                        }
                        disabled={entry.state === "pending" || busy === entry.name}
                        onClick={() => setOpened(entry.name)}
                      >
                        <PenLine />
                      </Button>
                    </div>
                    {entry.reason ? (
                      <p className="text-small text-attention">{entry.reason}</p>
                    ) : null}
                    {entry.failed_pages > 0 ? (
                      <p className="text-small text-destructive">
                        {plural("transcribe.failedPages", entry.failed_pages)}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </CardContent>

      {opened ? (
        <DocumentDialog
          key={opened}
          kind={slot.kind}
          name={opened}
          onClose={() => setOpened(null)}
        />
      ) : null}
    </Card>
  );
}

export function TranscriptionSection({ slots }: { slots: RawSlot[] }) {
  const { t } = useT();
  if (!slots.some((slot) => slot.files.length > 0)) return null;

  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h3 className="font-display font-expanded text-heading">{t("transcribe.title")}</h3>
        <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
          {t("transcribe.intro1")}
        </p>
        <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
          {t("transcribe.intro2")}
        </p>
        <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
          {t("transcribe.intro3")}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {slots.map((slot) => (
          <SlotTranscription key={slot.kind} slot={slot} />
        ))}
      </div>
    </section>
  );
}
