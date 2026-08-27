import { Ban, Hammer, Hourglass, PenLine, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type { DocumentState, TranscriptionState } from "./types";
import { useT, type Key, type Translate } from "@/lib/i18n";

/**
 * THE TRANSCRIPTION OF ONE RAW SLOT, IN THREE PIECES THAT A ROW ARRANGES.
 *
 * It used to be a card per slot in a grid of its own, under a three-paragraph heading, so
 * an instance with two stocked slots spent four cards and ~600 px of the panel on
 * something that is true of two folders. The pieces are the same; what changed is that the
 * slot is one row now (`RawSection`) and each of these answers one question of it: what
 * state is it in, what can I press, and what is inside.
 *
 * They each read the same query — react-query dedupes it — so a row can place them where
 * it needs them without threading state through props.
 */

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

function useSlot(slot: RawSlot) {
  const hasFiles = slot.files.length > 0;
  const state = useTranscription(slot.kind, hasFiles);
  const running = useTranscribing(slot.kind);
  const data = state.data;
  return {
    hasFiles,
    loading: state.isLoading,
    data,
    running,
    todo: (data?.pending ?? 0) + (data?.stale ?? 0),
  };
}

/** What state the slot's documents are in, as one badge. */
export function TranscriptionBadge({ slot }: { slot: RawSlot }) {
  const { t, plural } = useT();
  const { hasFiles, data, running } = useSlot(slot);

  if (!hasFiles || !data) return null;
  if (running) return <Badge mark={<Spinner className="size-3" />}>{t("transcribe.transcribing")}</Badge>;
  if (data.stale > 0)
    return <Badge variant="attention">{plural("transcribe.staleCount", data.stale)}</Badge>;
  if (data.pending > 0)
    return <Badge variant="outline">{plural("transcribe.pendingCount", data.pending)}</Badge>;
  return <Badge variant="settled">{t("transcribe.upToDate")}</Badge>;
}

/**
 * WHAT CHANGED, on the row itself.
 *
 * A badge saying «2 caducados» reports the state and not the cause, and the register's
 * rule is that staleness is a state with a reason or it is not a state at all. The reasons
 * repeat across documents — it is the model, the DPI, the OCR or the prompt that moved —
 * so they are deduped and read as one line.
 */
export function TranscriptionNote({ slot }: { slot: RawSlot }) {
  const { data } = useSlot(slot);
  if (!data || data.stale === 0) return null;

  const reasons = [...new Set(data.documents.map((entry) => entry.reason).filter(Boolean))];
  if (reasons.length === 0) return null;

  return <p className="text-small text-attention">{reasons.join(" · ")}</p>;
}

/**
 * The one button: start what is missing, or stop what is running.
 *
 * Nothing to do and nothing running renders NOTHING — the badge already says «al día», and
 * a disabled button beside it is a second drawing of the same fact. Every other reason it
 * cannot be pressed (read-only, engine down, already queued) keeps the button, disabled,
 * with the reason in its tooltip: that is the case the explanation exists for.
 */
export function TranscriptionAction({ slot }: { slot: RawSlot }) {
  const { t } = useT();
  const { hasFiles, data, running, todo } = useSlot(slot);
  const run = useTranscribeRun(slot.kind);
  const start = useStartTranscription();
  const cancel = useCancelJob();
  const offline = useEngineOffline();
  const canEdit = useCanEdit();

  if (!hasFiles || !data) return null;

  if (running) {
    return (
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
    );
  }

  const reason = !canEdit
    ? t("build.readOnly")
    : offline
      ? offline
      : start.isPending
        ? t("common.sending")
        : null;

  if (todo === 0 && !reason) return null;

  return (
    <Button
      size="sm"
      variant={data.stale > 0 && data.pending === 0 ? "outline" : "default"}
      disabled={Boolean(reason) || todo === 0}
      title={
        reason ??
        (todo === 0
          ? t("transcribe.allDone")
          : data.done > 0
            ? t("transcribe.startHintSome")
            : t("transcribe.startHintNone"))
      }
      onClick={() => start.mutate(slot.kind)}
    >
      {start.isPending ? <Spinner /> : data.stale > 0 ? <RefreshCw /> : <Hammer />}
      {launchLabel(data.pending, data.stale, data.done, t)}
    </Button>
  );
}

function RunningBlock({ slot }: { slot: RawSlot }) {
  const { t } = useT();
  const run = useTranscribeRun(slot.kind);
  const phases = useTranscribePhases();
  const overall = run?.overall ?? null;
  const queued = run?.job?.status === "queued";
  // Two nested loops, drawn as two bars: which document of how many, and how far into that
  // document's pages (or, once they are done, into its seams).
  const docs = documentLoop(run);
  const inner = innerLoop(run);

  return (
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
      </div>

      {queued ? null : (
        <>
          {overall && phases.length > 0 ? (
            <PhaseBar phases={phases} percent={overall.percent} activeKey={overall.key} />
          ) : (
            <Progress value={overall?.percent ?? 0} max={100} />
          )}
          {overall?.detail ? (
            <p className="truncate text-small text-muted-foreground">{overall.detail}</p>
          ) : null}

          {/* The inner loop, drawn as its own bar: the outer one moves once per document,
              so on a corpus of long PDFs it would sit still for as long as it takes to read
              one — which reads as a stall and is not. */}
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
      )}
    </div>
  );
}

function DocumentList({ slot, data }: { slot: RawSlot; data: TranscriptionState }) {
  const { t, plural } = useT();
  const run = useTranscribeRun(slot.kind);
  const [opened, setOpened] = useState<string | null>(null);
  // The one document nobody may correct while this runs: the transcriber rewrites its whole
  // directory at the end, so an edit saved into it now would be discarded without a word.
  const busy = busyDocument(run);

  if (data.documents.length === 0) return null;

  return (
    <>
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
                variant={busy === entry.name ? "outline" : (STATE[entry.state]?.variant ?? "outline")}
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
            {entry.reason ? <p className="text-small text-attention">{entry.reason}</p> : null}
            {entry.failed_pages > 0 ? (
              <p className="text-small text-destructive">
                {plural("transcribe.failedPages", entry.failed_pages)}
              </p>
            ) : null}
          </li>
        ))}
      </ul>

      {opened ? (
        <DocumentDialog
          key={opened}
          kind={slot.kind}
          name={opened}
          onClose={() => setOpened(null)}
        />
      ) : null}
    </>
  );
}

/** What is inside the slot: the run while there is one, and every document with its state. */
export function TranscriptionDetail({ slot }: { slot: RawSlot }) {
  const { t, plural } = useT();
  const { hasFiles, loading, data, running } = useSlot(slot);

  if (!hasFiles) return <p className="text-small text-muted-foreground">{t("transcribe.noDocuments")}</p>;
  if (loading) return <Skeleton className="h-20" />;
  if (!data) {
    return (
      <Alert tone="danger" title={t("transcribe.unreadable")}>
        <p>{t("transcribe.noResponse", { path: `/api/raw/${slot.kind}/transcription` })}</p>
      </Alert>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-small nums text-muted-foreground">
        {plural("transcribe.documents", data.documents.length)}
        {data.total_pages > 0 ? plural("transcribe.pages", data.total_pages) : ""}
        {t("transcribe.oneCallPerPage")}
      </p>
      {running ? <RunningBlock slot={slot} /> : null}
      <DocumentList slot={slot} data={data} />
    </div>
  );
}
