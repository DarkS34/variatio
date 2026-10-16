/** The process: the engine's health and the installation's door. */

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Key } from "@/lib/i18n";
import { useHasWorkspace } from "../auth";
import { keys } from "./keys";

// `enabled` on both of the shell's queries, and on nothing else: they fire from the header
// on every screen, and with no workspace they would only 403. A screen that reads an
// instance is never reached in that state.
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
 * Asked without a session and by every tab: the poll is what turns a screen into the notice
 * seconds after the switch is thrown rather than at the next reload. `retry: false` because
 * a server that is not answering is not a closed door, and the gate reads a failure here as
 * "open", never as "closed".
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
 * Why no job can be launched right now, or `null`.
 *
 * Every job kind calls a model, so without an engine none can succeed; the server already
 * refuses with a 503 and this only keeps the button from asking. While `/health` has not
 * answered nothing is blocked: a button disabled out of ignorance is worse than one that
 * fails once.
 */
export function useEngineOffline(): Key | null {
  const health = useHealth();
  if (!health.data) return null;
  return health.data.available ? null : ("engine.offline" as Key);
}
