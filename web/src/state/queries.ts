import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { useToast } from "@/components/ui/toast";
import { api, getScope } from "@/lib/api";
import { localeStore, translator, useT, type Key, type Language } from "@/lib/i18n";
import { phaseName } from "@/lib/names";
import { isSplitEngine, ownedBy, queuedNotice, readLanes } from "@/lib/queue";
import type {
  ArtifactName,
  BuildPhase,
  CommissionScope,
  EvaluatorProfile,
  JobKind,
  Lanes,
  RawKind,
  Role,
  WorkspaceRow,
} from "@/lib/types";
import { authKeys, useHasWorkspace, useSession } from "./auth";
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
 *
 * It is also how a screen finds ITS run now that two lanes let two jobs run at once:
 * «el trabajo en curso» is no longer a single thing, so the generate screen asks for a
 * generation and the evaluation screen for a comparison instead of both taking whatever
 * the stream last heard from. `accept` narrows further — pass a module-level function, or
 * the memo re-runs every render.
 */
export function useJobRun(
  kind: JobKind,
  accept?: (run: RunView) => boolean,
): RunView | null {
  const stream = useStream();
  return useMemo(() => {
    const runs = Object.values(stream.runs).filter(
      (run) => run.job?.kind === kind && (!accept || accept(run)),
    );
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, kind, accept]);
}

/**
 * The most recent run of this kind that THIS account launched.
 *
 * The stream carries the whole workspace, so `useJobRun` alone adopts a colleague's run:
 * with two evaluators on `/evaluate`, the second one's screen collapsed onto the first
 * one's comparison — and then onto its 404. The generate and evaluation screens are
 * about a commission somebody made, so they filter by author; the build screens stay on
 * `useJobRun`, because an artifact under construction is under construction for everyone.
 * `ownedBy` fails open when either id is unknown, so an older API degrades to the shared
 * behaviour instead of hiding the run.
 */
export function useOwnJobRun(
  kind: JobKind,
  accept?: (run: RunView) => boolean,
): RunView | null {
  const me = useSession().data?.user.id;
  const stream = useStream();
  return useMemo(() => {
    const runs = Object.values(stream.runs).filter(
      (run) =>
        run.job?.kind === kind && ownedBy(run.job, me) && (!accept || accept(run)),
    );
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, kind, accept, me]);
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
export function useEngineOffline(): Key | null {
  const health = useHealth();
  if (!health.data) return null;
  return health.data.available ? null : ("engine.offline" as Key);
}

export function usePipeline() {
  return useQuery({
    queryKey: keys.pipeline,
    queryFn: api.pipeline,
    refetchInterval: (query) => (query.state.data?.queue_length ? 5_000 : false),
    enabled: useHasWorkspace(),
  });
}

/**
 * The state of the two queues, one per inference backend, or null.
 *
 * Null is «this server does not split the queue», not a failure: an API older than this
 * bundle sends no `lanes` and every reader has a flat fallback. Reading `data.lanes.local`
 * straight would blank the screen on exactly that skew, which is a failure this project
 * has already made once.
 */
export function useLanes(): Lanes | null {
  const pipeline = usePipeline();
  return useMemo(() => readLanes(pipeline.data), [pipeline.data]);
}

/** Whether «el motor» is two halves worth telling apart, as the engine's own name says. */
export function useSplitEngine(): boolean {
  return isSplitEngine(useHealth().data?.engine);
}

/**
 * The three reads a commission is composed from, optionally about a NAMED instance.
 *
 * With no argument they are what they always were: the tab's workspace, the tab's cache
 * entry. With one, the slug goes into the query key as well as into the header — two
 * instances sharing `["kg"]` would serve one graph as the other's, which is the whole
 * class of bug the `X-Workspace` header exists to prevent, moved into the cache. The base
 * key stays a prefix of the named one, so every `invalidateQueries` already written
 * reaches both.
 */
const scoped = <K extends readonly unknown[]>(key: K, workspace?: string | null) =>
  workspace ? ([...key, workspace] as const) : key;

export function useProfile(workspace?: string | null) {
  return useQuery({
    queryKey: scoped(keys.profile, workspace),
    queryFn: () => api.profile(workspace),
  });
}

export function useContentContext() {
  return useQuery({ queryKey: keys.context, queryFn: api.context });
}

export function useKg(workspace?: string | null) {
  return useQuery({ queryKey: scoped(keys.kg, workspace), queryFn: () => api.kg(workspace) });
}

export function useKgGraph(workspace?: string | null) {
  return useQuery({
    queryKey: scoped(keys.kgGraph, workspace),
    queryFn: () => api.kgGraph(workspace),
  });
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

// Gated like `useHealth`, and it became necessary the moment the shell started reading it:
// `/api/raw` resolves a membership like every route, so an account that belongs to no
// workspace would only ever get a 403 out of it. Every other consumer already sits behind
// a screen that needs an instance.
export function useRaw() {
  return useQuery({ queryKey: keys.raw, queryFn: api.raw, enabled: useHasWorkspace() });
}

/** The phase plan of every builder: what the segmented bar is a drawing of. */
export function useBuildPlans() {
  return useQuery({
    queryKey: keys.phases,
    queryFn: api.buildPhases,
    staleTime: Infinity,
  });
}

/**
 * A plan with every phase named in the reader's language.
 *
 * Named here rather than in `PhaseBar`: the bar is handed a plan with no idea WHICH plan it
 * is, and a phase key only means something inside its own — `convert` is three different
 * phases across the three builders. The two hooks below are the one place that holds both
 * halves, and naming it here is also what covers every bar at once.
 */
function namedPhases(
  plan: string,
  phases: BuildPhase[] | undefined,
  t: (key: Key) => string,
): BuildPhase[] {
  if (!phases) return [];
  return phases.map((phase) => ({ ...phase, label: phaseName(plan, phase.key, t, phase.label) }));
}

/** The phases of one build, in order. Empty until the plan has arrived, which is what
 *  makes the bar fall back to the plain one instead of drawing a single wrong segment. */
export function useBuildPhases(artifact: ArtifactName | undefined): BuildPhase[] {
  const plans = useBuildPlans();
  const { t } = useT();
  if (!artifact) return [];
  return namedPhases(artifact, plans.data?.artifacts?.[artifact], t);
}

/**
 * What the commission's free-text field may ask for, for one modality.
 *
 * `staleTime: Infinity` like the phase plan: it is derived from artifacts a generation
 * run cannot change, and switching workspace clears the whole cache anyway.
 */
export function useScope(itemType: string | null, workspace?: string | null) {
  return useQuery<CommissionScope>({
    queryKey: scoped(keys.scope(itemType ?? ""), workspace),
    queryFn: () => getScope(itemType!, workspace),
    enabled: Boolean(itemType),
    staleTime: Infinity,
  });
}

/** The same for a job that writes no artifact and still has phases. */
export function useJobPhases(kind: JobKind): BuildPhase[] {
  const plans = useBuildPlans();
  const { t } = useT();
  return namedPhases(kind, plans.data?.jobs?.[kind], t);
}

/**
 * The KIND of the raw slot this artifact needs and that has no documents, or null.
 *
 * Which slot feeds which artifact is declared by the server (`slot.feeds`), so the
 * screens never carry a second copy of that mapping. What comes back is the kind and not
 * the label, because the label is the API's own language: `lib/raw.slotLabelOf` is where
 * it becomes the reader's.
 */
export function useRawMissingFor(artifact: ArtifactName | undefined): RawKind | null {
  const raw = useRaw();
  if (!artifact) return null;
  const slot = (raw.data?.slots ?? []).find(
    (candidate) => candidate.feeds.includes(artifact) && candidate.files.length === 0,
  );
  return slot?.kind ?? null;
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

/**
 * Drop everything the instance we have just left put on screen.
 *
 * `removeQueries`, and never `client.clear()`: clearing does not empty a query, it
 * DESTROYS it, so the observers of `["auth","me"]` — the gate and `useHasWorkspace` —
 * stay bound to a dead object and never hear the fresh answer.
 */
function dropInstanceQueries(client: QueryClient) {
  client.removeQueries({
    predicate: (query) => !NOT_ABOUT_AN_INSTANCE.includes(query.queryKey[0] as string),
  });
}

/**
 * Put the stream back wherever the account has ended up.
 *
 * The tab is pointing at nothing, and where it lands next is `me`'s answer rather than
 * this tab's — the server reassigns the account when the workspace it was in disappears.
 * So the socket waits for that answer instead of reconnecting into the void: a handshake
 * for an account in no workspace is refused with 4401, and «la sesión ha caducado» is the
 * one thing that is not happening. `useSession` adopts the new slug as it arrives.
 */
function relandStream(client: QueryClient) {
  runStore.forget();
  void client.refetchQueries({ queryKey: authKeys.me }).then(() => {
    if (activeWorkspace()) runStore.connect();
  });
}

/**
 * Move the tab out of an instance that has just stopped existing.
 *
 * The deletion's own answer says where this account lands, so the tab goes STRAIGHT there
 * instead of to `null` and back — `me` would say the same thing a round trip later, and in
 * between the header reads «ningún workspace» and the panel offers to create one, over a
 * change that only moved you to the workspace next door. `set` before dropping the queries,
 * so what refetches afterwards already carries the new `X-Workspace`.
 *
 * `relandStream` is still what reconnects: `me` is the authority on whether the landing is
 * real, and a socket opened for an account in no workspace closes with 4401 — which reads
 * as «la sesión ha caducado», the one thing that is not happening.
 */
function leaveDeleted(client: QueryClient, landed: string | null) {
  workspaceStore.set(landed);
  dropInstanceQueries(client);
  relandStream(client);
}

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
      dropInstanceQueries(client);
      if (landed) {
        client.invalidateQueries({ queryKey: authKeys.me });
        runStore.reset();
      } else {
        relandStream(client);
      }
    },
  });
}

export function useSwitchWorkspace() {
  return useLandIn((slug: string) => api.activateWorkspace(slug));
}

export function useCreateWorkspace() {
  return useLandIn(
    ({ slug, name, language }: { slug: string; name: string; language: Language }) =>
      api.createWorkspace(slug, name, language),
  );
}

/**
 * The owner disposing of one of their own instances, which since 2026-08-28 is any one they
 * own and not only the one they are standing in — the call carries its own `X-Workspace`.
 *
 * So it cannot go through `useLandIn` any more: that forgets the tab's slug unconditionally,
 * which is right when what went is the instance on screen and pure churn when it is not.
 * Deleting the one you are in takes the same door as switching — the tab drops its slug and
 * `me` says where the account wakes up — and never `client.clear()`, which destroys
 * `["auth","me"]` instead of emptying it and leaves the header naming a workspace that no
 * longer exists.
 */
export function useDeleteWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.deleteWorkspace(slug),
    onSuccess: ({ deleted, landed }) => {
      if (deleted === activeWorkspace()) {
        leaveDeleted(client, landed);
      } else {
        client.invalidateQueries({ queryKey: authKeys.me });
      }
      client.invalidateQueries({ queryKey: keys.workspaces });
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
 *
 * Deleting the one you are IN used to `client.clear()`, which is the one thing the login
 * gate's rule forbids: it destroys `["auth","me"]` instead of emptying it, so the very
 * query that says where this account lands next notifies nobody and the header keeps the
 * name of a workspace that no longer exists. It takes the same door as switching now — the
 * tab forgets its slug, the instance's queries go, and `me` says where it wakes up.
 */
/**
 * Renaming an instance, which only an administrator does (2026-08-28, explicit user
 * request). It invalidates the panel AND the switcher: the header carries the name of the
 * workspace this tab has open, and it is the same row.
 */
export function useAdminRenameWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, name }: { slug: string; name: string }) =>
      api.adminRenameWorkspace(slug, name),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin"] });
      client.invalidateQueries({ queryKey: keys.workspaces });
      client.invalidateQueries({ queryKey: authKeys.me });
    },
  });
}

export function useAdminDeleteWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.adminDeleteWorkspace(slug),
    onSuccess: ({ deleted, landed }) => {
      if (deleted === activeWorkspace()) {
        // Every request would otherwise carry the dead slug in `X-Workspace`.
        leaveDeleted(client, landed);
      } else {
        client.invalidateQueries({ queryKey: authKeys.me });
      }
      client.invalidateQueries({ queryKey: ["admin"] });
      client.invalidateQueries({ queryKey: keys.workspaces });
    },
  });
}

/**
 * Say, once and briefly, that what was just launched is going to wait.
 *
 * The notice is about the WAIT and not about the launch: a job that starts straight away
 * has nothing to announce, and the criterion for «is it waiting» is the payload's, shared
 * with the pending state every button holds afterwards. Every launcher goes through here,
 * so no screen carries a second copy of the rule.
 */
export function useQueuedNotice() {
  const toast = useToast();
  const lanes = useLanes();
  const split = useSplitEngine();
  return (job: Parameters<typeof queuedNotice>[0]) => {
    const notice = queuedNotice(job, lanes, split, translator(localeStore.getSnapshot()));
    if (notice) toast(notice);
  };
}

export function useSubmitJob() {
  const invalidate = useInvalidateChain();
  const announce = useQueuedNotice();
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
      announce(job);
      invalidate();
    },
  });
}

/** A generation writes a row, so the saved-variants list is part of the chain now. */

export function useCancelJob() {
  return useMutation({ mutationFn: (id: string) => api.cancelJob(id) });
}

