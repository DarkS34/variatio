/** The administration panel's readings and gestures. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ArtifactName, FeatureMode, GatedName, InviteTerms, Role } from "@/lib/types";
import { authKeys } from "../auth";
import { keys } from "./keys";
import { useInvalidateChain } from "./pipeline";

/**
 * The same door, read by the account that can close it.
 *
 * A second query and not a parameter: the public answer deliberately omits WHO closed it.
 * No poll — the panel is where it changes.
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
 * Ending a subject's course, the administrator's alone: it moves the people, their counts and
 * the class link at once, in the panel and in the class of a subject the tab has open.
 */
export function useAdminEndCourse() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, action }: { slug: string; action: "disable" | "remove" }) =>
      api.adminEndCourse(slug, action),
    onSettled: () => {
      client.invalidateQueries({ queryKey: ["admin"] });
      client.invalidateQueries({ queryKey: keys.members });
      client.invalidateQueries({ queryKey: keys.workspaces });
    },
  });
}

export function useAdminOverview() {
  return useQuery({ queryKey: keys.adminOverview, queryFn: api.adminOverview });
}

export function useAdminWorkspaceGenerations(
  slug: string,
  params: { author?: number; q?: string; limit?: number; offset?: number },
) {
  return useQuery({
    queryKey: keys.adminGenerations(slug, params),
    queryFn: () => api.adminWorkspaceGenerations(slug, params),
    placeholderData: (previous) => previous,
  });
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

/** What the queue has finished since the API started, newest first; it lives in memory. */
export function useAdminJobHistory() {
  return useQuery({
    queryKey: keys.adminJobHistory,
    queryFn: () => api.adminJobHistory(30),
    refetchInterval: 10_000,
  });
}

/** Empty the panel's list of finished jobs; the jobs stay readable by their authors. */
export function useAdminClearJobHistory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.adminClearJobHistory(),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.adminJobHistory }),
  });
}

/**
 * The engine's reading, polled: residency and the tunnel change on their own, and a model
 * being pulled moves every second.
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
    makeTeacher: useMutation({
      mutationFn: (id: number) => api.adminMakeTeacher(id),
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

/** Who each optional function is for: its mode and the accounts on its list. */
export function useAdminFeatures() {
  return useQuery({ queryKey: keys.adminFeatures, queryFn: api.adminFeatures });
}

/**
 * Set who one optional function is for; `accounts` absent keeps its list as it is.
 *
 * The session is refreshed too: the administrator is not exempt from the rule, so the
 * change may open or close a door in their own bar.
 */
export function useSetFeature() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      feature,
      mode,
      accounts,
      workspaces,
    }: {
      feature: GatedName;
      mode: FeatureMode;
      accounts?: number[];
      workspaces?: string[];
    }) =>
      api.adminSetFeature(feature, {
        mode,
        ...(accounts ? { accounts } : {}),
        ...(workspaces ? { workspaces } : {}),
      }),
    onSuccess: (payload) => {
      // The answer IS the new state, so the panel draws it at once rather than flashing the
      // old one until the refetch lands.
      client.setQueryData(keys.adminFeatures, payload);
      client.invalidateQueries({ queryKey: keys.adminFeatures });
      client.invalidateQueries({ queryKey: authKeys.me });
    },
  });
}

export function useAdminInvites() {
  return useQuery({ queryKey: keys.adminInvites, queryFn: api.adminInvites });
}

export function useCreateInvites() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: InviteTerms & { count: number }) => api.adminCreateInvites(body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.adminInvites }),
  });
}

export function useImportInvite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: InviteTerms & { link: string }) => api.adminImportInvite(body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.adminInvites }),
  });
}

/**
 * One invitation's link, read while its panel is open and forgotten when it closes.
 *
 * `gcTime: 0` is the point: the listing never carries a link, so that a live credential sits
 * in the page only while somebody is looking at it, and reopening the panel is a fresh read
 * the server writes down. The key is NOT under `adminInvites`, or every create, edit and
 * revoke would re-read — and re-log — whichever link happens to be open. A query rather than
 * a mutation fired from an effect: React's development double-mount detaches a mutation's
 * observer, and the answer then never reaches the panel.
 */
/** Every subject's live class link, for the administrator's «Asignaturas» tab. */
export function useAdminClassLinks() {
  return useQuery({ queryKey: keys.adminClassLinks, queryFn: api.adminClassLinks });
}

/** Pausing, resuming or retiring a subject's class link from the panel. */
export function useAdminClassLinkActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: keys.adminClassLinks });
  return {
    pause: useMutation({
      mutationFn: ({ id, paused }: { id: number; paused: boolean }) =>
        api.adminPauseClassLink(id, paused),
      onSettled: refresh,
    }),
    revoke: useMutation({ mutationFn: api.adminRevokeClassLink, onSettled: refresh }),
  };
}

export function useInviteLink(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "invite-link", id] as const,
    queryFn: () => api.adminInviteLink(id),
    enabled,
    retry: false,
    staleTime: Infinity,
    gcTime: 0,
  });
}

export function useEditInvite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: Partial<InviteTerms> }) =>
      api.adminEditInvite(id, changes),
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
 * Both refresh the session as well as the overview: the account being moved may be the
 * administrator's own, and the switcher would keep offering an instance they just left.
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
    enable: useMutation({
      mutationFn: ({ id, workspace }: { id: number; workspace: string }) =>
        api.adminEnableMembership(id, workspace),
      onSuccess: refresh,
    }),
  };
}

/**
 * Removing an account for good.
 *
 * The whole `["admin", …]` prefix goes and not just the overview: the account was also a
 * group in "por cuenta" and possibly the evaluation tab's current filter.
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
 * Invalidates the chain as well as `["admin"]`: the workspace may be the one this tab has
 * open, and then what is on screen has just stopped existing on disk.
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
 * Renaming an instance, which only an administrator does.
 *
 * It invalidates the panel AND the switcher: the header carries the name of the workspace
 * this tab has open, and it is the same row.
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
