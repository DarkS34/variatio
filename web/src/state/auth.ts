import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import type { Role, Session } from "@/lib/types";

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
    queryFn: api.me,
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useIsUnauthenticated(query: ReturnType<typeof useSession>) {
  return query.isError && query.error instanceof ApiError && query.error.status === 401;
}

/** Everything the app knows is scoped to the session, so a change wipes the whole cache. */
function useAdopt() {
  const client = useQueryClient();
  return (session: Session | null) => {
    client.clear();
    if (session) client.setQueryData(authKeys.me, session);
  };
}

export function useLogin() {
  const adopt = useAdopt();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.login(email, password),
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
  return useMutation({
    mutationFn: api.acceptInvite,
    onSuccess: (result) => {
      if (result.created) adopt(result);
    },
  });
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
