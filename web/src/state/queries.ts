import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { api } from "@/lib/api";
import type {
  ArtifactName,
  EvaluationDetail,
  EvaluationParams,
  EvaluationRating,
} from "@/lib/types";
import { runStore, type RunView } from "./runStore";

export const keys = {
  health: ["health"] as const,
  pipeline: ["pipeline"] as const,
  profile: ["profile"] as const,
  kg: ["kg"] as const,
  kgGraph: ["kg", "graph"] as const,
  descriptions: ["kg", "descriptions"] as const,
  bank: (params: Record<string, unknown>) => ["bank", params] as const,
  coverage: ["bank", "coverage"] as const,
  jobs: ["jobs"] as const,
  raw: ["raw"] as const,
  evaluations: ["evaluations"] as const,
  evaluation: (id: string) => ["evaluations", id] as const,
};

export function useStream() {
  return useSyncExternalStore(runStore.subscribe, runStore.getSnapshot, runStore.getSnapshot);
}

/** The most recent run that builds this artifact, running or not. */
export function useArtifactRun(artifact: ArtifactName | undefined): RunView | null {
  const stream = useStream();
  return useMemo(() => {
    if (!artifact) return null;
    const runs = Object.values(stream.runs).filter((run) => run.job?.artifact === artifact);
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, artifact]);
}

/** A wall clock that only ticks while something is running. */
export function useElapsed(startedAt: number | null | undefined, live: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [live]);
  if (!startedAt) return null;
  return Math.max(0, (now - startedAt) * 1000);
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health, refetchInterval: 15_000 });
}

export function usePipeline() {
  return useQuery({ queryKey: keys.pipeline, queryFn: api.pipeline });
}

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: api.profile });
}

export function useKg() {
  return useQuery({ queryKey: keys.kg, queryFn: api.kg });
}

export function useKgGraph() {
  return useQuery({ queryKey: keys.kgGraph, queryFn: api.kgGraph });
}

export function useDescriptions() {
  return useQuery({ queryKey: keys.descriptions, queryFn: api.descriptions });
}

export function useCoverage() {
  return useQuery({ queryKey: keys.coverage, queryFn: api.coverage });
}

export function useRaw() {
  return useQuery({ queryKey: keys.raw, queryFn: api.raw });
}

/**
 * The label of the raw slot this artifact needs and that has no documents, or null.
 *
 * Which slot feeds which artifact is declared by the server (`slot.feeds`), so the
 * screens never carry a second copy of that mapping.
 */
export function useRawMissingFor(artifact: ArtifactName | undefined): string | null {
  const raw = useRaw();
  if (!artifact) return null;
  const slot = (raw.data?.slots ?? []).find(
    (candidate) => candidate.feeds.includes(artifact) && candidate.files.length === 0,
  );
  return slot?.label ?? null;
}

/** Everything an artifact write can invalidate, in one place. */
export function useInvalidateChain() {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: keys.pipeline });
    client.invalidateQueries({ queryKey: keys.kg });
    client.invalidateQueries({ queryKey: keys.kgGraph });
    client.invalidateQueries({ queryKey: keys.descriptions });
    client.invalidateQueries({ queryKey: ["bank"] });
    client.invalidateQueries({ queryKey: keys.profile });
  };
}

export function useSubmitJob() {
  const invalidate = useInvalidateChain();
  return useMutation({
    mutationFn: ({
      kind,
      params,
      force,
    }: {
      kind: string;
      params?: Record<string, unknown>;
      force?: boolean;
    }) => api.submitJob(kind, params ?? {}, force ?? false),
    onSuccess: ({ job }) => {
      runStore.setCurrentJob(job.id);
      invalidate();
    },
  });
}

export function useCancelJob() {
  return useMutation({ mutationFn: (id: string) => api.cancelJob(id) });
}

/* Evaluation ----------------------------------------------------------------------- */

export function useEvaluations(limit = 50) {
  return useQuery({ queryKey: keys.evaluations, queryFn: () => api.evaluations(limit) });
}

export function useEvaluation(id: string | null) {
  return useQuery({
    queryKey: keys.evaluation(id ?? "none"),
    queryFn: () => api.evaluation(id!),
    enabled: Boolean(id),
  });
}

export function useLaunchEvaluation() {
  return useMutation({
    mutationFn: (params: EvaluationParams) => api.launchEvaluation(params),
    onSuccess: ({ job }) => runStore.setCurrentJob(job.id),
  });
}

/** The choice and the rubric both return the whole session, so the cache takes the
 *  response instead of refetching: the reveal must be instant, not a second round trip. */
function useSessionMutation<T>(call: (id: string, payload: T) => Promise<EvaluationDetail>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: T }) => call(id, payload),
    onSuccess: (detail) => {
      client.setQueryData(keys.evaluation(detail.session.id), detail);
      client.invalidateQueries({ queryKey: keys.evaluations });
    },
  });
}

export function useChooseProposal() {
  return useSessionMutation<{ choice: number | null; comment?: string }>((id, payload) =>
    api.chooseEvaluation(id, payload.choice, payload.comment),
  );
}

export function useRateSession() {
  return useSessionMutation<Partial<EvaluationRating>>((id, payload) =>
    api.rateEvaluation(id, payload),
  );
}
