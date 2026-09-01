import { Check, Hourglass } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { PhaseBar, Progress, Spinner } from "@/components/ui/misc";
import { phaseName, stepName } from "@/lib/names";
import type { RawSlot } from "@/lib/types";

import { documentLoop, innerLoop, loopLabel } from "./progress";
import {
  TRANSCRIBE_JOB,
  useTranscribePhases,
  useTranscribeRun,
  useTranscribing,
  useTranscription,
} from "./queries";
import { useT } from "@/lib/i18n";

/**
 * THE TRANSCRIPTION OF ONE RAW SLOT, IN THE TWO PIECES ITS CARD ARRANGES.
 *
 * Each answers one question about the slot — what state is it in, and what is happening
 * right now — and they read the same query, which react-query dedupes, so `SlotCard` can
 * place them where it needs them without threading state through props.
 *
 * There is no per-origin BUTTON any more (2026-09-01, explicit user request). Reading the
 * documents is one press for the whole screen, in the alert at the top, and two buttons
 * doing the same work on two halves of one action is exactly the kind of choice this
 * branch exists to remove. Nothing is lost with it: the global one appears under the same
 * condition the two used to, and it fans out per slot.
 *
 * Two more pieces used to live here and are gone rather than moved. `TranscriptionNote`
 * deduplicated the staleness reasons across the whole slot because the panel had one row
 * per origin and nowhere to put a per-document cause; with one row per DOCUMENT the cause
 * sits on the row it belongs to, which is where it was always meant to be. `DocumentList`
 * went the same way — it listed the same filenames a second time, beside a size it did not
 * know about.
 */


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
  const run = useTranscribeRun(slot.kind);

  if (!hasFiles || !data) return null;
  if (running)
    return (
      <Badge mark={<Spinner className="size-3" />}>
        {run?.cancelling ? t("common.stopping") : t("transcribe.transcribing")}
      </Badge>
    );
  if (data.stale > 0)
    return <Badge variant="attention">{plural("transcribe.staleCount", data.stale)}</Badge>;
  if (data.pending > 0)
    return <Badge variant="outline">{plural("transcribe.pendingCount", data.pending)}</Badge>;
  // A TICK AND NOT THE WORDS «al día» (2026-09-01, explicit user request). The state with
  // nothing left to do is the one a person scans past, and a mark reads faster than a word
  // in a row of words. `Badge` is what draws it, so the circle carries the same measured
  // 8 % tint as every other badge; `p-0` and a fixed size are what turn the pill into a
  // circle. The word survives as the accessible name — colour and shape are not a channel
  // for a screen reader.
  return (
    <Badge
      variant="attention"
      className="size-6 justify-center p-0"
      title={t("transcribe.upToDate")}
    >
      <Check aria-hidden />
      <span className="sr-only">{t("transcribe.upToDate")}</span>
    </Badge>
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