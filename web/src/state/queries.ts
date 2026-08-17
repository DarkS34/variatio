import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { api } from "@/lib/api";
import type {
  ArtifactName,
  BuildPhase,
  EvaluationDetail,
  EvaluationParams,
  EvaluationRating,
  Role,
} from "@/lib/types";
import { runStore, type RunView } from "./runStore";
import { workspaceStore } from "./workspace";

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
  // The phase plan of each builder. It is a property of the code, not of the instance, so
  // it is fetched once and never invalidated — nothing a user does can change it.
  phases: ["pipeline", "phases"] as const,
  evaluations: ["evaluations"] as const,
  evaluation: (id: string) => ["evaluations", id] as const,
  generations: (params: Record<string, unknown>) => ["generations", params] as const,
  generation: (id: number) => ["generations", "one", id] as const,
  workspaces: ["workspaces"] as const,
  adminOverview: ["admin", "overview"] as const,
  adminInvites: ["admin", "invites"] as const,
  adminEvaluations: (filters: Record<string, unknown>) =>
    ["admin", "evaluations", filters] as const,
};

/** The slug this tab is looking at, as a React value. */
export function useActiveWorkspace() {
  return useSyncExternalStore(
    workspaceStore.subscribe,
    workspaceStore.getSnapshot,
    workspaceStore.getSnapshot,
  );
}

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

/** The phase plan of every builder: what the segmented bar is a drawing of. */
export function useBuildPlans() {
  return useQuery({
    queryKey: keys.phases,
    queryFn: api.buildPhases,
    staleTime: Infinity,
  });
}

/** The phases of one build, in order. Empty until the plan has arrived, which is what
 *  makes the bar fall back to the plain one instead of drawing a single wrong segment. */
export function useBuildPhases(artifact: ArtifactName | undefined): BuildPhase[] {
  const plans = useBuildPlans();
  if (!artifact) return [];
  return plans.data?.artifacts?.[artifact] ?? [];
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
    client.invalidateQueries({ queryKey: ["generations"] });
  };
}

/* Workspaces ----------------------------------------------------------------------- */

export function useWorkspaces() {
  return useQuery({ queryKey: keys.workspaces, queryFn: api.workspaces });
}

/**
 * Move this tab to another instance.
 *
 * Three things have to happen together and in this order: the server records the
 * preference, the tab starts sending the new header, and everything cached under the old
 * one is dropped. Doing the last one first would refetch with the old header; skipping it
 * would leave the previous graph on screen under the new name.
 */
export function useSwitchWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.activateWorkspace(slug),
    onSuccess: ({ workspace }) => {
      workspaceStore.set(workspace.slug);
      client.clear();
      runStore.reset();
    },
  });
}

export function useCreateWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, name }: { slug: string; name: string }) =>
      api.createWorkspace(slug, name),
    onSuccess: ({ workspace }) => {
      workspaceStore.set(workspace.slug);
      client.clear();
      runStore.reset();
    },
  });
}

export function useDeleteWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.deleteWorkspace(slug),
    onSuccess: () => {
      workspaceStore.set(null);
      client.clear();
      runStore.reset();
    },
  });
}

/* Saved variants -------------------------------------------------------------------- */

export function useGenerations(params: {
  scope?: "mine" | "workspace";
  concept?: string;
  q?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: keys.generations(params),
    queryFn: () => api.generations(params),
    placeholderData: (previous) => previous,
  });
}

export function useGeneration(id: number | null) {
  return useQuery({
    queryKey: keys.generation(id ?? 0),
    queryFn: () => api.generation(id!),
    enabled: id !== null,
  });
}

export function useDeleteGeneration() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteGeneration(id),
    onSuccess: () => client.invalidateQueries({ queryKey: ["generations"] }),
  });
}

/* Administration -------------------------------------------------------------------- */

export function useAdminOverview() {
  return useQuery({ queryKey: keys.adminOverview, queryFn: api.adminOverview });
}

export function useAdminEvaluations(filters: {
  workspace?: string | null;
  account?: number | null;
}) {
  return useQuery({
    queryKey: keys.adminEvaluations(filters),
    queryFn: () => api.adminEvaluations(filters),
    placeholderData: (previous) => previous,
  });
}

export function useSetAccountEnabled() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      api.setAccountEnabled(id, enabled),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.adminOverview }),
  });
}

export function useAdminInvites() {
  return useQuery({ queryKey: keys.adminInvites, queryFn: api.adminInvites });
}

export function useCreateInvite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { workspace: string | null; role: Role }) =>
      api.adminCreateInvite(body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.adminInvites }),
  });
}

export function useRevokeInvite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.adminRevokeInvite(id),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.adminInvites }),
  });
}

/**
 * Granting and revoking access, from the one screen that does it.
 *
 * Both refresh the overview — which is where the roles are read from — and also the
 * session, because the account being moved may be the administrator's own and the
 * workspace switcher would otherwise keep offering an instance they just left.
 */
export function useMembershipActions() {
  const client = useQueryClient();
  const refresh = () => {
    client.invalidateQueries({ queryKey: keys.adminOverview });
    client.invalidateQueries({ queryKey: ["auth", "me"] });
    client.invalidateQueries({ queryKey: keys.workspaces });
  };
  return {
    grant: useMutation({
      mutationFn: ({ id, workspace, role }: { id: number; workspace: string; role: Role }) =>
        api.adminGrantMembership(id, workspace, role),
      onSuccess: refresh,
    }),
    revoke: useMutation({
      mutationFn: ({ id, workspace }: { id: number; workspace: string }) =>
        api.adminRevokeMembership(id, workspace),
      onSuccess: refresh,
    }),
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

/** A generation writes a row, so the saved-variants list is part of the chain now. */

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
