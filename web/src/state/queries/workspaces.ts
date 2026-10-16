/** The subjects of an account, and landing elsewhere when one goes. */

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { api } from "@/lib/api";
import type { Language } from "@/lib/i18n";
import type { WorkspaceRow } from "@/lib/types";
import { authKeys } from "../auth";
import { runStore } from "../runStore";
import { activeWorkspace, workspaceStore } from "../workspace";
import { keys } from "./keys";

/** The slug this tab is looking at, as a React value. */
export function useActiveWorkspace() {
  return useSyncExternalStore(
    workspaceStore.subscribe,
    workspaceStore.getSnapshot,
    workspaceStore.getSnapshot,
  );
}

export function useWorkspaces() {
  return useQuery({ queryKey: keys.workspaces, queryFn: api.workspaces });
}

/**
 * What survives leaving an instance: the session, and the state of the installation's door.
 *
 * `["maintenance"]` is read by the gate itself, so dropping it would put the whole app back
 * on its loading spinner for as long as the poll takes.
 */
const NOT_ABOUT_AN_INSTANCE = ["auth", "maintenance"];

/**
 * Drop everything the instance we have just left put on screen.
 *
 * `removeQueries`, and NEVER `client.clear()`: clearing does not empty a query, it DESTROYS
 * it, so the observers of `["auth","me"]` — the gate and `useHasWorkspace` — stay bound to
 * a dead object and never hear the fresh answer.
 */
function dropInstanceQueries(client: QueryClient) {
  client.removeQueries({
    predicate: (query) => !NOT_ABOUT_AN_INSTANCE.includes(query.queryKey[0] as string),
  });
}

/**
 * Put the stream back wherever the account has ended up.
 *
 * Where it lands next is `me`'s answer and not this tab's, so the socket waits for it
 * instead of reconnecting into the void: a handshake for an account in no workspace is
 * refused with 4401, which reads as "la sesión ha caducado".
 */
function relandStream(client: QueryClient) {
  runStore.forget();
  void client.refetchQueries({ queryKey: authKeys.me }).then(() => {
    if (activeWorkspace()) runStore.connect();
  });
}

/**
 * Move the tab out of an instance this account has just lost: a teacher removed or paused
 * its membership while the tab was open on it (`not_member`, `membership_disabled`, or the
 * stream closed with 4403).
 *
 * The tab forgets its own choice — the header it sends is what the server refuses — and
 * lands wherever `me` says the account is now. Every query in flight is refused at once and
 * each one calls this, so only the first does anything until the session has answered.
 */
let leaving = false;

export function leaveLostWorkspace(client: QueryClient) {
  if (leaving) return;
  leaving = true;
  workspaceStore.set(null);
  dropInstanceQueries(client);
  runStore.forget();
  void client
    .refetchQueries({ queryKey: authKeys.me })
    .finally(() => {
      leaving = false;
      if (activeWorkspace()) runStore.connect();
    });
}

/**
 * Move the tab out of an instance that has just stopped existing.
 *
 * The deletion's own answer says where this account lands, so the tab goes STRAIGHT there
 * rather than to `null` and back through `me` — in between, the header would read "ninguna
 * asignatura" over a change that only moved you to the workspace next door. `set` before
 * dropping the queries, so what refetches afterwards carries the new `X-Workspace`.
 */
function leaveDeleted(client: QueryClient, landed: string | null) {
  workspaceStore.set(landed);
  dropInstanceQueries(client);
  relandStream(client);
}

/**
 * Land this tab in an instance — another one, a new one, or none at all.
 *
 * Three things happen together and in this order: the tab starts sending the new header,
 * everything cached under the old one is dropped, and `me` is asked again. The other order
 * refetches with the old header; skipping the drop leaves the previous graph on screen
 * under the new name.
 */
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
 * The owner disposing of one of their own instances, which is any one they own: the call
 * carries its own `X-Workspace`.
 *
 * So it cannot go through `useLandIn`, which forgets the tab's slug unconditionally —
 * right when what went is the instance on screen, pure churn when it is not.
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

/**
 * Remove any workspace from the panel, active or not.
 *
 * The administrator's version of `useDeleteWorkspace` and deliberately not the same hook:
 * emptying the cache is right only when the one gone is this tab's, and pure churn when the
 * deletion is of another instance.
 */
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
