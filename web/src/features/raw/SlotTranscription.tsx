import { Ban, Hammer, Hourglass, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PhaseBar, Progress, Spinner } from "@/components/ui/misc";
import { phaseName, stepName } from "@/lib/names";
import type { RawSlot } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import { useCancelJob, useEngineOffline } from "@/state/queries";

import { documentLoop, innerLoop, loopLabel } from "./progress";
import {
  TRANSCRIBE_JOB,
  useStartTranscription,
  useTranscribePhases,
  useTranscribeRun,
  useTranscribing,
  useTranscription,
} from "./queries";
import { useT, type Translate } from "@/lib/i18n";

/**
 * THE TRANSCRIPTION OF ONE RAW SLOT, IN THE THREE PIECES ITS CARD ARRANGES.
 *
 * Each answers one question about the slot — what state is it in, what is there to press,
 * and what is happening right now — and they each read the same query, which react-query
 * dedupes, so `SlotCard` can place them where it needs them without threading state
 * through props.
 *
 * Two more pieces used to live here and are gone rather than moved. `TranscriptionNote`
 * deduplicated the staleness reasons across the whole slot because the panel had one row
 * per origin and nowhere to put a per-document cause; with one row per DOCUMENT the cause
 * sits on the row it belongs to, which is where it was always meant to be. `DocumentList`
 * went the same way — it listed the same filenames a second time, beside a size it did not
 * know about.
 */


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

export function RunningBlock({ slot }: { slot: RawSlot }) {
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
          {/* The phase, or the outer loop's step when the plan has not arrived: both come
              with the API's own sentence. This job's plan is filed under its kind, since
              it writes no artifact. */}
          {queued
            ? t("transcribe.queued")
            : ((overall?.label
                ? phaseName(TRANSCRIBE_JOB, overall.key, t, overall.label)
                : null) ??
              (docs ? stepName(docs.id, t, docs.label) : null) ??
              t("transcribe.preparing"))}
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
                  {inner.detail ?? stepName(inner.id, t, inner.label)}
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