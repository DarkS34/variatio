import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import type { Role, Session } from "@/lib/types";
import { runStore } from "./runStore";
import { workspaceStore } from "./workspace";

export const authKeys = {
  me: ["auth", "me"] as const,
  invites: ["auth", "invites"] as const,
  members: ["auth", "members"] as const,
};

/**
 * Who is looking, or a 401.
 *
 * `retry: false` matters: a 401 is an answer, not a failure to reach the server, and
 * retrying it three times only delays the login form by a second for no reason.
 */
export function useSession() {
  return useQuery({
    queryKey: authKeys.me,
    // The tab learns its workspace here and nowhere else, and it learns it *before* the
    // query resolves — so no child has rendered, and no request has gone out without the
    // `X-Workspace` header. Doing it in an effect would be too late: effects run
    // child-first, and the WebSocket is opened by one of those children.
    queryFn: async () => {
      const session = await api.me();
      workspaceStore.adopt(session.active_workspace);
      return session;
    },
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useIsUnauthenticated(query: ReturnType<typeof useSession>) {
  return query.isError && query.error instanceof ApiError && query.error.status === 401;
}

const isSessionKey = (key: readonly unknown[]) =>
  key.length === authKeys.me.length && key.every((part, index) => part === authKeys.me[index]);

/**
 * Everything the app knows is scoped to the session, so a change wipes the whole cache.
 * The workspace goes with it: a new login lands on that account's own instance, and a
 * logout must not leave the next person's tab pointing at the previous one's.
 *
 * Everything EXCEPT the session query, which is the one thing the gate is watching.
 * `client.clear()` used to take that one too, and clearing does not empty a query — it
 * *destroys* it and drops it from the cache. The gate's observer stays bound to the
 * destroyed object, so the fresh query `setQueryData` builds underneath it never notifies
 * anybody: the login form keeps rendering against a session that has already arrived, and
 * only a reload — which builds a new observer — makes it go away. That was the «entro y la
 * página no cambia hasta que la refresco» bug. Writing into the live query instead keeps
 * the observer and the data on the same object, which is the whole contract.
 */
function useAdopt() {
  const client = useQueryClient();
  return (session: Session | null) => {
    workspaceStore.set(session?.active_workspace ?? null);
    // Coming in, the stream has to be re-subscribed to the new account's workspace; going
    // out there is nothing to subscribe to, and reconnecting would only earn a 4401.
    if (session) runStore.reset();
    else runStore.forget();
    client.removeQueries({ predicate: (query) => !isSessionKey(query.queryKey) });

    if (session) client.setQueryData(authKeys.me, session);
    // On the way out there is no session to write, and "logged out" is not a value: it is
    // the 401 the server answers. Refetching through the same live query is what turns the
    // gate around, and `retry: false` means it costs exactly one request.
    else client.resetQueries({ queryKey: authKeys.me });
  };
}

export function useLogin() {
  const adopt = useAdopt();
  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      api.login(username, password),
    onSuccess: adopt,
  });
}

export function useLogout() {
  const adopt = useAdopt();
  return useMutation({
    mutationFn: api.logout,
    // The cookie is gone either way; a failed logout must still drop what is on screen.
    onSettled: () => adopt(null),
  });
}

export function useAcceptInvite() {
  const adopt = useAdopt();
  return useMutation({ mutationFn: api.acceptInvite, onSuccess: adopt });
}

export function useResetPassword() {
  const adopt = useAdopt();
  return useMutation({
    mutationFn: ({ token, password }: { token: string; password: string }) =>
      api.resetPassword(token, password),
    onSuccess: adopt,
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ current, next }: { current: string; next: string }) =>
      api.changePassword(current, next),
  });
}

export function useInvites(enabled: boolean) {
  return useQuery({ queryKey: authKeys.invites, queryFn: api.invites, enabled });
}

export function useMembers(enabled: boolean) {
  return useQuery({ queryKey: authKeys.members, queryFn: api.members, enabled });
}

export function useCreateInvite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createInvite,
    onSuccess: () => client.invalidateQueries({ queryKey: authKeys.invites }),
  });
}

export function useRevokeInvite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.revokeInvite,
    onSuccess: () => client.invalidateQueries({ queryKey: authKeys.invites }),
  });
}

export function useMemberActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: authKeys.members });
  return {
    setRole: useMutation({
      mutationFn: ({ id, role }: { id: number; role: Role }) => api.setMemberRole(id, role),
      onSuccess: refresh,
    }),
    remove: useMutation({ mutationFn: api.removeMember, onSuccess: refresh }),
  };
}

/**
 * May this session change anything here?
 *
 * The server decides for real — every mutating route hangs off `require_member(EDITOR)` —
 * and this is only what keeps the UI from offering a control that would 403. Defaults to
 * `false` while the session is loading, so nothing flashes as enabled and then locks.
 */
export function useCanEdit() {
  const session = useSession();
  return session.data?.role === "editor" || session.data?.role === "owner";
}

export function useIsOwner() {
  return useSession().data?.role === "owner";
}

export const ROLE_LABELS: Record<Role, string> = {
  viewer: "Lectura",
  editor: "Edición",
  owner: "Propietario",
};

export const ROLE_HINTS: Record<Role, string> = {
  viewer: "Ve la instancia y el historial; no construye, no edita, no genera.",
  editor: "Todo lo anterior, más construir, editar, aprobar y generar.",
  owner: "Todo lo anterior, más invitar personas y cambiar sus roles.",
};
