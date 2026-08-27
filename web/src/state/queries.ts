import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { api, getScope } from "@/lib/api";
import type {
  ArtifactName,
  BuildPhase,
  CommissionScope,
  EvaluatorProfile,
  JobKind,
  Role,
  WorkspaceRow,
} from "@/lib/types";
import { authKeys, useHasWorkspace } from "./auth";
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
  adminJobHistory: ["admin", "jobs", "history"] as const,
  adminEngine: ["admin", "engine"] as const,
  maintenance: ["maintenance"] as const,
  adminMaintenance: ["admin", "maintenance"] as const,
  adminSystem: ["admin", "system"] as const,
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

// `enabled` on both of the shell's queries, and on nothing else: with no workspace every
// route that reads an instance answers 403, and these two are the ones that fire from the
// header on every screen — polled, at that. The screens' own queries stay as they are,
// because a screen that reads an instance is not reached in that state.
export function useHealth() {
  return useQuery({
    queryKey: keys.health,
    queryFn: api.health,
    refetchInterval: 15_000,
    enabled: useHasWorkspace(),
  });
}

/**
 * Is the installation closed?
 *
 * Asked without a session and by every tab, because the state can change while somebody is
 * working: the poll is what turns a screen into the notice a couple of dozen seconds after
 * the switch is thrown, instead of at the next reload. `retry: false` for the same reason
 * the session query has it — a server that is not answering is not the same statement as a
 * closed door, and the gate treats a failure here as «open», never as «closed».
 */
export function useMaintenance() {
  return useQuery({
    queryKey: keys.maintenance,
    queryFn: api.maintenance,
    refetchInterval: 20_000,
    refetchOnWindowFocus: true,
    retry: false,
    staleTime: 10_000,
  });
}

/**
 * The same door, read by the account that can close it.
 *
 * A second query rather than a parameter on the first, because the two answers are not the
 * same answer: the public one deliberately omits WHO closed it, and the panel is the one
 * place that gets to say so. No poll — the panel is where it changes.
 */
export function useAdminMaintenance() {
  return useQuery({ queryKey: keys.adminMaintenance, queryFn: api.adminMaintenance });
}

export function useSetMaintenance() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ active, message }: { active: boolean; message: string | null }) =>
      api.setMaintenance(active, message),
    // Both copies at once: the panel's own row and the one every screen's gate reads.
    onSuccess: (state) => {
      client.setQueryData(keys.adminMaintenance, state);
      client.setQueryData(keys.maintenance, state);
    },
  });
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
    enabled: useHasWorkspace(),
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
 * Land this tab in an instance — another one, a new one, or none at all.
 *
 * Three things have to happen together and in this order: the tab starts sending the new
 * header, everything cached under the old one is dropped, and `me` is asked again. Doing
 * the second one first would refetch with the old header; skipping it would leave the
 * previous graph on screen under the new name.
 *
 * `removeQueries` and NEVER `client.clear()`, which is the part that had to change when
 * the default workspace went away. Clearing does not empty a query, it DESTROYS it and
 * drops it from the cache, so the observers of `["auth","me"]` — the gate and
 * `useHasWorkspace` — stay bound to a dead object and never hear the fresh answer. That
 * did not show while every account always had an instance and `role` never changed as one
 * moved between them. Now it does: entering the first workspace turns `null` into a role
 * and deleting the last one turns it back, and a screen that misses that either keeps
 * offering «crea el tuyo» over a workspace that already exists or the reverse.
 *
 * What survives is what is not about an instance: the session, and the state of the
 * installation's door. `["maintenance"]` is read by the gate itself, so dropping it puts
 * the whole app back on its loading spinner for as long as the poll takes — a blink of
 * «cargando» over a change that only concerns which graph is on screen.
 */
const NOT_ABOUT_AN_INSTANCE = ["auth", "maintenance"];

function useLandIn<TInput, TResult extends object>(
  mutationFn: (input: TInput) => Promise<TResult>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      // No `workspace` in the answer is a deletion: the tab is left pointing at nothing,
      // and where it lands next is `me`'s to say.
      const landed = (data as { workspace?: WorkspaceRow }).workspace;
      workspaceStore.set(landed?.slug ?? null);
      client.removeQueries({
        predicate: (query) => !NOT_ABOUT_AN_INSTANCE.includes(query.queryKey[0] as string),
      });
      client.invalidateQueries({ queryKey: authKeys.me });
      runStore.reset();
    },
  });
}

export function useSwitchWorkspace() {
  return useLandIn((slug: string) => api.activateWorkspace(slug));
}

export function useCreateWorkspace() {
  return useLandIn(({ slug, name }: { slug: string; name: string }) =>
    api.createWorkspace(slug, name),
  );
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
  // Through the same door as entering one: leaving your last workspace is what turns the
  // panel back into the offer to create one, and only a re-read of `me` says so.
  return useLandIn((slug: string) => api.deleteWorkspace(slug));
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

export function usePromoteGeneration() {
  const invalidate = useInvalidateChain();
  return useMutation({
    mutationFn: (id: number) => api.promoteGeneration(id),
    onSuccess: () => invalidate(),
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

export function useAdminJobHistory() {
  return useQuery({
    queryKey: keys.adminJobHistory,
    queryFn: () => api.adminJobHistory(50),
    refetchInterval: 10_000,
  });
}

/**
 * The engine's reading, polled: residency and the tunnel change on their own, and a model
 * being pulled moves every second. Five seconds while something is in flight, thirty when
 * nothing is.
 */
export function useAdminEngine() {
  return useQuery({
    queryKey: keys.adminEngine,
    queryFn: api.adminEngine,
    refetchInterval: (query) => {
      const data = query.state.data;
      const moving =
        data?.pulls.some((pull) => pull.status === "running") ||
        (data?.tunnel.wanted && !data.tunnel.running);
      return moving ? 2_000 : 15_000;
    },
  });
}

export function useAdminSystem() {
  return useQuery({ queryKey: keys.adminSystem, queryFn: api.adminSystem });
}

function useEngineMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.adminEngine });
      client.invalidateQueries({ queryKey: keys.adminOverview });
      client.invalidateQueries({ queryKey: keys.health });
    },
  });
}

export function useEngineActions() {
  return {
    release: useEngineMutation(() => api.adminReleaseGpu()),
    pull: useEngineMutation((model: string) => api.adminPullModel(model)),
    remove: useEngineMutation((model: string) => api.adminDeleteModel(model)),
    invalidateAll: useEngineMutation(() => api.adminInvalidateContexts()),
    invalidate: useEngineMutation((slug: string) => api.adminInvalidateContext(slug)),
    tunnelStart: useEngineMutation(() => api.adminTunnelStart()),
    tunnelStop: useEngineMutation(() => api.adminTunnelStop()),
  };
}

/** The account-level controls beyond enable/disable: the flag, the sessions, the lock. */
export function useAccountActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: keys.adminOverview });
  return {
    setAdmin: useMutation({
      mutationFn: ({ id, isAdmin }: { id: number; isAdmin: boolean }) =>
        api.adminSetAdmin(id, isAdmin),
      onSuccess: refresh,
    }),
    setProfile: useMutation({
      mutationFn: ({ id, profile }: { id: number; profile: EvaluatorProfile | null }) =>
        api.adminSetProfile(id, profile),
      onSuccess: refresh,
    }),
    resetLink: useMutation({ mutationFn: (id: number) => api.adminResetLink(id) }),
    revokeSessions: useMutation({
      mutationFn: (id: number) => api.adminRevokeSessions(id),
      onSuccess: refresh,
    }),
    unlock: useMutation({
      mutationFn: (id: number) => api.adminUnlockLogin(id),
      onSuccess: refresh,
    }),
  };
}

export function useClearCache() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.adminClearCache(slug),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.adminOverview });
      client.invalidateQueries({ queryKey: keys.adminEngine });
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

