import { Check } from "lucide-react";

import { JobProgress } from "@/components/BuildProgress";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/misc";
import type { RawSlot } from "@/lib/types";

import { useTranscribePhases, useTranscribeRun, useTranscribing, useTranscription } from "./queries";
import { useT } from "@/lib/i18n";

/**
 * THE TRANSCRIPTION OF ONE RAW SLOT, IN THE TWO PIECES ITS CARD ARRANGES.
 *
 * Each answers one question about the slot — what state is it in, and what is happening
 * right now — and they read the same query, which react-query dedupes, so `SlotCard` can
 * place them where it needs them without threading state through props.
 *
 * There is no per-origin BUTTON any more (2026-09-01, explicit user request). Reading the
 * documents is one press for the whole screen, in the block at the top, and two buttons
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
  // A TICK AND NOT THE WORDS «al día» (2026-09-01, explicit user request), and since
  // 2026-09-02 a FILLED one (also explicit user request: «más vistoso»). The state with
  // nothing left to do is the one a person scans past, and a mark reads faster than a word
  // in a row of words. It was the 8 % badge tint; that tint is the whole card's now
  // (`SlotCard`), so the mark on that ground has to be solid to be seen at all —
  // `--attention` under its own foreground, the pair `check:color` measures. The word
  // survives as the accessible name — colour and shape are not a channel for a screen
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
 * The slot's transcription while it runs, drawn as EVERY OTHER JOB IS.
 *
 * It was a bordered block of its own — two bars, no clock, no percentage, no job name —
 * and the stop button sat in the alert at the top of the screen under the word «Detener»,
 * while a building stage draws a `JobProgress` card with «Cancelar» inside it. One card
 * for the four steps now (2026-09-02, explicit user request: the same convention for every
 * step of the construction). Nothing is lost by it: the step timeline the card draws
 * already groups the document loop and the inner one (pages, pictures, seams) as one row
 * each, with the counter and the bar the old block drew by hand.
 *
 * The stop button takes BOTH live runs, not this slot's alone: «Leerlos todos ahora» starts
 * one job per origin, and a stop on one card that left the other running is what had the
 * button pressed twice for one press of the launcher.
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
