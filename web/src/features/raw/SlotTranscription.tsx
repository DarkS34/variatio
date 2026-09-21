import { Check } from "lucide-react";

import { JobProgress } from "@/components/BuildProgress";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/misc";
import type { RawSlot } from "@/lib/types";

import { useTranscribePhases, useTranscribeRun, useTranscribing, useTranscription } from "./queries";
import { useT } from "@/lib/i18n";

/**
 * The transcription of one raw slot, in the two pieces its card arranges.
 *
 * Each answers one question about the slot — what state is it in, and what is happening
 * right now — and they read the same query, which react-query dedupes, so `SlotCard` can
 * place them without threading state through props.
 *
 * There is no per-origin BUTTON: reading the documents is one press for the whole screen,
 * which fans out per slot. A per-document staleness cause sits on the row it belongs to.
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
    todo: (data?.pending ?? 0) + (data?.stale ?? 0) + (data?.retry ?? 0),
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
  // Read, but with pages to try again: the tick would say "nothing left", which is not true.
  if ((data.retry ?? 0) > 0)
    return <Badge variant="danger">{plural("transcribe.retryCount", data.retry ?? 0)}</Badge>;
  // A filled tick and not the words "al día": the state with nothing left to do is the one
  // a person scans past, and a mark reads faster than a word in a row of words. Solid,
  // because the 8 % tint is the whole card's (`SlotCard`) and a tinted mark on it would
  // vanish — `--attention` under its own foreground, the pair `check:color` measures. The
  // word survives as the accessible name: colour and shape are not a channel for a screen
  // reader.
  return (
    <span
      className="flex size-7 shrink-0 items-center justify-center rounded-full bg-attention text-attention-foreground"
      title={t("transcribe.upToDate")}
    >
      <Check aria-hidden className="size-4" strokeWidth={3} />
      <span className="sr-only">{t("transcribe.upToDate")}</span>
    </span>
  );
}

/**
 * The slot's transcription while it runs, drawn as every other job is: one `JobProgress`
 * card for the four steps of the construction.
 *
 * The stop button takes BOTH live runs and not this slot's alone: "Leerlos todos ahora"
 * starts one job per origin, so stopping one card and leaving the other running means the
 * button has to be pressed twice for one press of the launcher.
 */
export function RunningBlock({ slot }: { slot: RawSlot }) {
  const { t } = useT();
  const run = useTranscribeRun(slot.kind);
  const phases = useTranscribePhases();
  const corpus = useTranscribeRun("corpus");
  const exemplars = useTranscribeRun("exemplars");
  const live = [corpus, exemplars].filter(
    (entry) => entry?.job?.status === "running" || entry?.job?.status === "queued",
  );

  return (
    <JobProgress
      run={run}
      phases={phases}
      waiting={t("transcribe.preparing")}
      cancel={{ runs: live, word: "stop", hint: t("transcribe.stopHint") }}
    />
  );
}
