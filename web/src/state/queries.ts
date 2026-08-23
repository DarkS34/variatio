import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { api, getScope } from "@/lib/api";
import type {
  ArtifactName,
  BuildPhase,
  CommissionScope,
  JobKind,
  Role,
} from "@/lib/types";
import { runStore, type RunView } from "./runStore";
import { activeWorkspace, workspaceStore } from "./workspace";

export const keys = {
  health: ["health"] as const,
  pipeline: ["pipeline"] as const,
  profile: ["profile"] as const,
  context: ["context"] as const,
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
  // Keyed by modality, because the fields a modality declares are half of what decides
  // the owners: two modalities of one instance do not have the same scope.
  scope: (itemType: string) => ["pipeline", "scope", itemType] as const,
  generations: (params: Record<string, unknown>) => ["generations", params] as const,
  generation: (id: number) => ["generations", "one", id] as const,
  workspaces: ["workspaces"] as const,
  adminOverview: ["admin", "overview"] as const,
  adminInvites: ["admin", "invites"] as const,
  adminJobs: ["admin", "jobs"] as const,
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

/**
 * The most recent run of a job of this kind, running or not.
 *
 * `useArtifactRun` cannot answer this: it keys on the artifact a build writes, and the
 * jobs that have no artifact — describing concepts, indexing, tagging — are exactly the
 * ones whose screen has nowhere else to show that something is happening.
 */
export function useJobRun(kind: JobKind): RunView | null {
  const stream = useStream();
  return useMemo(() => {
    const runs = Object.values(stream.runs).filter((run) => run.job?.kind === kind);
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, kind]);
}

/** True while a job of this kind is queued or running, whoever launched it. */
export function useJobRunning(kind: JobKind): boolean {
  const run = useJobRun(kind);
  const status = run?.job?.status;
  return status === "running" || status === "queued";
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

/**
 * Why no job can be launched right now, or `null`.
 *
 * All nine job kinds call a model, so without an engine none can succeed. It lives here and
 * not in each screen because the server already refuses with a 503: this is what keeps the
 * button from even asking. While `/health` has not answered yet nothing is blocked — a
 * button disabled out of ignorance is worse than one that fails once.
 */
export function useEngineOffline(): string | null {
  const health = useHealth();
  if (!health.data) return null;
  return health.data.available ? null : "El motor de inferencia no responde.";
}

export function usePipeline() {
  return useQuery({
    queryKey: keys.pipeline,
    queryFn: api.pipeline,
    refetchInterval: (query) => (query.state.data?.queue_length ? 5_000 : false),
  });
}

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: api.profile });
}

export function useContentContext() {
  return useQuery({ queryKey: keys.context, queryFn: api.context });
}

export function useKg() {
  return useQuery({ queryKey: keys.kg, queryFn: api.kg });
}

export function useKgGraph() {
  return useQuery({ queryKey: keys.kgGraph, queryFn: api.kgGraph });
}

/**
 * The descriptions, and while they are being written, refreshed on their own.
 *
 * The writer saves after each concept — cancelling loses nothing — but the screen only asked
 * again when the job finished or when the tab regained focus, so the list filled in jumps
 * and by surprise. With the job running it asks every few seconds, which is the pace they
 * are written at.
 */
export function useDescriptions() {
  const live = useJobRunning("describe_concepts");
  return useQuery({
    queryKey: keys.descriptions,
    queryFn: api.descriptions,
    refetchInterval: live ? 4_000 : false,
  });
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
 * What the commission's free-text field may ask for, for one modality.
 *
 * `staleTime: Infinity` like the phase plan: it is derived from artifacts a generation
 * run cannot change, and switching workspace clears the whole cache anyway.
 */
export function useScope(itemType: string | null) {
  return useQuery<CommissionScope>({
    queryKey: keys.scope(itemType ?? ""),
    queryFn: () => getScope(itemType!),
    enabled: Boolean(itemType),
    staleTime: Infinity,
  });
}

/** The same for a job that writes no artifact and still has phases. */
export function useJobPhases(kind: JobKind): BuildPhase[] {
  const plans = useBuildPlans();
  return plans.data?.jobs?.[kind] ?? [];
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

export function useRenameWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, name }: { slug: string; name: string }) =>
      api.renameWorkspace(slug, name),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["workspaces"] });
      client.invalidateQueries({ queryKey: ["auth", "me"] });
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

export function useAdminJobs() {
  return useQuery({
    queryKey: keys.adminJobs,
    queryFn: api.adminJobs,
    refetchInterval: 3000,
  });
}

export function useAdminCancelJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.adminCancelJob(id),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.adminJobs });
      client.invalidateQueries({ queryKey: keys.adminOverview });
    },
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

/**
 * Removing an account for good.
 *
 * The whole `["admin", …]` prefix goes, not just the overview: the deleted account was a
 * row in the accounts table, a group in «por cuenta» and possibly the current filter of
 * the study tab, and leaving any of those cached shows a name that no longer exists.
 */
export function useDeleteAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteAccount(id),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin"] }),
  });
}

/**
 * Empty a stage from the administration panel.
 *
 * Invalidates `["admin"]` and the chain too: the affected workspace may be the one this tab
 * has open, and then what is on screen — the graph, the profile, the bank — has just stopped
 * existing on disk.
 */
export function useDeleteArtifact() {
  const client = useQueryClient();
  const invalidate = useInvalidateChain();
  return useMutation({
    mutationFn: ({ slug, artifact }: { slug: string; artifact: ArtifactName }) =>
      api.adminDeleteArtifact(slug, artifact),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin"] });
      invalidate();
    },
  });
}

/**
 * Remove a whole workspace from the panel, which is any one and not the active one.
 *
 * It is the administrator's version of `useDeleteWorkspace`, and cannot be the same one:
 * that one deletes the instance you are in and therefore empties the whole cache and
 * releases the switcher. Here that only applies when the one gone turns out to be this tab's;
 * in the normal case the deletion is of another instance and dropping the cache would reload
 * the screen for no reason.
 */
export function useAdminDeleteWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.adminDeleteWorkspace(slug),
    onSuccess: ({ deleted }) => {
      if (deleted === activeWorkspace()) {
        workspaceStore.set(null);
        client.clear();
        runStore.reset();
        return;
      }
      client.invalidateQueries({ queryKey: ["admin"] });
      client.invalidateQueries({ queryKey: keys.workspaces });
      client.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
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

