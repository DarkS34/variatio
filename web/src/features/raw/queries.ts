import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import type { BuildPhase, JobKind, RawKind, RawSlot } from "@/lib/types";
import { useBuildPlans, useStream } from "@/state/queries";
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
  const plans = useBuildPlans();
  return plans.data?.jobs?.[TRANSCRIBE_JOB] ?? [];
}

export function useTranscription(kind: RawKind, enabled = true) {
  const live = useTranscribing(kind);
  return useQuery({
    queryKey: rawKeys.transcription(kind),
    queryFn: () => rawApi.transcription(kind),
    enabled,
    refetchInterval: live ? 4_000 : false,
  });
}

export function useTranscriptionSummary(slots: RawSlot[]) {
  const stocked = (kind: RawKind) =>
    slots.some((slot) => slot.kind === kind && slot.files.length > 0);

  const corpus = useTranscription("corpus", stocked("corpus"));
  const exemplars = useTranscription("exemplars", stocked("exemplars"));
  const corpusRunning = useTranscribing("corpus");
  const exemplarsRunning = useTranscribing("exemplars");

  const states = [corpus.data, exemplars.data].filter((entry) => entry !== undefined);
  return {
    running: corpusRunning || exemplarsRunning,
    stale: states.reduce((sum, entry) => sum + entry.stale, 0),
    pending: states.reduce((sum, entry) => sum + entry.pending, 0),
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
