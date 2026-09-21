import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";

import type { BuildPhase, Job, JobKind, RawKind, RawSlot } from "@/lib/types";
import { useJobPhases, useStream } from "@/state/queries";
import { runStore, type RunView } from "@/state/runStore";

import { rawApi } from "./api";
import type { DocumentPages } from "./types";

export const TRANSCRIBE_JOB: JobKind = "transcribe";

export const rawKeys = {
  transcription: (kind: RawKind) => ["raw", "transcription", kind] as const,
  document: (kind: RawKind, name: string) =>
    ["raw", "transcription", kind, name] as const,
};

export function useTranscribeRun(kind: RawKind): RunView | null {
  const stream = useStream();
  return useMemo(() => {
    const runs = Object.values(stream.runs).filter(
      (run) =>
        run.job?.kind === TRANSCRIBE_JOB && String(run.job.params?.["slot"]) === kind,
    );
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, kind]);
}

export function useTranscribing(kind: RawKind): boolean {
  const status = useTranscribeRun(kind)?.job?.status;
  return status === "running" || status === "queued";
}

export function useTranscribePhases(): BuildPhase[] {
  return useJobPhases(TRANSCRIBE_JOB);
}

/**
 * A slot's reading, refreshed while its job runs and read ONCE MORE the moment it stops.
 *
 * The poll is what draws the documents turning "leído" one by one; the last read is what
 * makes the end of the job visible. `_meta.json` is written at the very end, so the last
 * poll of the run can land before it and the poll stops with the job — without this the
 * screen kept the state of that poll until somebody reloaded the page.
 */
export function useTranscription(kind: RawKind, enabled = true) {
  const live = useTranscribing(kind);
  const client = useQueryClient();
  const wasLive = useRef(live);
  useEffect(() => {
    if (wasLive.current && !live) {
      client.invalidateQueries({ queryKey: rawKeys.transcription(kind) });
    }
    wasLive.current = live;
  }, [live, kind, client]);
  return useQuery({
    queryKey: rawKeys.transcription(kind),
    queryFn: () => rawApi.transcription(kind),
    enabled,
    refetchInterval: live ? 4_000 : false,
  });
}

/**
 * The whole workspace's raw material as one answer, because both the panel and the raw
 * screen have to decide the same thing from it: what the next step is.
 *
 * `todo` is what a global button would act on and `stocked` is what makes that button
 * meaningful at all — an installation with two empty origins has nothing to transcribe and
 * a different first step entirely.
 */
export function useTranscriptionSummary(slots: RawSlot[]) {
  const stocked = (kind: RawKind) =>
    slots.some((slot) => slot.kind === kind && slot.files.length > 0);

  const corpus = useTranscription("corpus", stocked("corpus"));
  const exemplars = useTranscription("exemplars", stocked("exemplars"));
  const corpusRunning = useTranscribing("corpus");
  const exemplarsRunning = useTranscribing("exemplars");

  const states = [corpus.data, exemplars.data].filter((entry) => entry !== undefined);
  const stale = states.reduce((sum, entry) => sum + entry.stale, 0);
  const pending = states.reduce((sum, entry) => sum + entry.pending, 0);
  // A document with failed pages is up to date and still has work in it: reading the slot
  // again is what tries those pages, so it counts toward the button that does it.
  const retry = states.reduce((sum, entry) => sum + (entry.retry ?? 0), 0);

  // `known` guards `done`: the foot of the screen reads it, and during the first second of
  // a load — before a slot's reading has landed — "nada pendiente" is true by ABSENCE.
  const known = (["corpus", "exemplars"] as const).every(
    (kind) => !stocked(kind) || (kind === "corpus" ? corpus.data : exemplars.data) !== undefined,
  );
  const running = corpusRunning || exemplarsRunning;
  const stockedAll = slots.length > 0 && slots.every((slot) => slot.files.length > 0);
  return {
    running,
    stale,
    pending,
    retry,
    todo: stale + pending + retry,
    // Both origins hold something and both readings have landed: what the foot of the
    // screen needs before it may say anything at all about the way on.
    stocked: stockedAll && known,
    empty: slots.length > 0 && slots.every((slot) => slot.files.length === 0),
    // Both origins hold something, every document is read and nothing is running: what the
    // next step actually wants, and not merely "nothing is outstanding".
    done: stockedAll && known && !running && stale + pending + retry === 0,
  };
}

export function useStartTranscription() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (kind: RawKind) => rawApi.startTranscription(kind),
    onSuccess: ({ job }, kind) => {
      runStore.setCurrentJob(job.id);
      client.invalidateQueries({ queryKey: rawKeys.transcription(kind) });
    },
  });
}

/**
 * TRANSCRIBE EVERYTHING, as one press over as many jobs as there are origins.
 *
 * Deliberately a fan-out in the client and not a job of its own on the server: a
 * transcription is scoped to a slot everywhere else — its progress, its cancel button, its
 * duplicate guard and its `params.slot` all key on it — and a third job kind covering both
 * would have to reproduce every one of those. Two jobs is also the honest picture of what
 * happens: they reserve the same lane, so the second waits for the first, and the queue
 * says so by itself.
 *
 * Sequential rather than concurrent because the submit is what claims the lane, and the
 * one submitted first should be the one that runs first. A slot that refuses — already
 * transcribing, nothing to do — must not stop the other, so each is caught on its own.
 */
export function useStartAllTranscriptions() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (kinds: RawKind[]) => {
      const started: Job[] = [];
      const refused: string[] = [];
      for (const kind of kinds) {
        try {
          const { job } = await rawApi.startTranscription(kind);
          started.push(job);
        } catch (exception) {
          refused.push((exception as Error).message);
        }
      }
      if (started.length === 0 && refused.length > 0) throw new Error(refused.join(" · "));
      return { started, refused };
    },
    onSuccess: ({ started }, kinds) => {
      // The first one, because that is the one that is actually running: `setCurrentJob`
      // decides which run the drawer opens on, and pointing it at the queued one would
      // show a bar that has not started.
      if (started[0]) runStore.setCurrentJob(started[0].id);
      for (const kind of kinds) {
        client.invalidateQueries({ queryKey: rawKeys.transcription(kind) });
      }
    },
  });
}

export function useDocumentPages(kind: RawKind, name: string | null) {
  return useQuery({
    queryKey: rawKeys.document(kind, name ?? ""),
    queryFn: () => rawApi.documentPages(kind, name!),
    enabled: Boolean(name),
  });
}

export function usePageActions(kind: RawKind, name: string | null) {
  const client = useQueryClient();
  const settle = (data: DocumentPages) => {
    client.setQueryData(rawKeys.document(kind, name ?? ""), data);
    client.invalidateQueries({ queryKey: rawKeys.transcription(kind) });
  };

  return {
    save: useMutation({
      mutationFn: ({ index, text }: { index: number; text: string }) =>
        rawApi.savePage(kind, name!, index, text),
      onSuccess: settle,
    }),
    insert: useMutation({
      mutationFn: ({ after, text }: { after: number; text: string }) =>
        rawApi.insertPage(kind, name!, after, text),
      onSuccess: settle,
    }),
    remove: useMutation({
      mutationFn: (index: number) => rawApi.deletePage(kind, name!, index),
      onSuccess: settle,
    }),
  };
}
