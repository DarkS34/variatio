import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// The `wdth` sheet and not `index.css`: it is the one that publishes the width axis, which
// is what lets the type scale encode a ROLE with the width of the letter rather than with
// yet another size. Archivo now serves BOTH `--font-sans` and `--font-display`, so this is
// the whole text face of the application and the axis stopped being a detail of two steps.
// Of the two families only Archivo ships a variable build — Fontsource publishes no
// @fontsource-variable/ibm-plex-mono — so the mono is the static one.
// These must be imported BEFORE ./index.css, or the @font-face rules land after the app's
// own cascade and the first paint falls back to the system stack.
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";

import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ConfirmProvider } from "./components/ui/confirm";
import { ToastProvider } from "./components/ui/toast";
import { AuthGate } from "./features/auth/AuthGate";
import { ApiError } from "./lib/api";
import { ensureCatalogue, localeStore } from "./lib/i18n";
import { RouterProvider } from "./lib/router";
import { authKeys } from "./state/auth";
import { leaveLostWorkspace } from "./state/queries";
import "./index.css";

/**
 * A door that closed while somebody was inside it: ask for the session again.
 *
 * The administrator closes the evaluation or the tutor from the panel, and the next request
 * of a screen still open on it answers 403 `feature_off`. Refetching the session is what
 * makes the door leave the bar and the route fall to "not found", instead of a screen that
 * fails request by request. A teacher removing or pausing this account's membership is the
 * same thing one level up — `not_member` or `membership_disabled` — and the tab leaves the
 * subject for wherever the session lands it.
 */
function onApiError(error: unknown) {
  if (!(error instanceof ApiError)) return;
  if (error.code === "feature_off") {
    void queryClient.invalidateQueries({ queryKey: authKeys.me });
  } else if (error.code === "not_member" || error.code === "membership_disabled") {
    leaveLostWorkspace(queryClient);
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onApiError }),
  mutationCache: new MutationCache({ onError: onApiError }),
  defaultOptions: {
    queries: {
      // The pipeline is one user editing files on one machine: refetching on focus
      // buys nothing and would fight with unsaved editor state.
      refetchOnWindowFocus: false,
      // A 401 or a 403 is an answer, not a failure to reach the server. Retrying it
      // only delays the login screen and doubles the load on a rate-limited endpoint.
      retry: (failureCount, error) =>
        error instanceof ApiError && error.status >= 400 && error.status < 500
          ? false
          : failureCount < 1,
      staleTime: 5_000,
    },
  },
});

const tree = (
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Inside the router — a notice may want to link somewhere — and OUTSIDE AuthGate,
          so the login and invitation screens can acknowledge an action too. */}
      <RouterProvider>
        <ToastProvider>
          {/* Beside the toasts and for the same reason: asking before an irreversible
              action is not a screen's own business, and eighteen `window.confirm` calls
              were the alternative. */}
          <ConfirmProvider>
            {/* The last floor: any render error below becomes a sentence and a reload
                button instead of a white page. It fixes nothing — it makes the next crash
                reportable. */}
            <ErrorBoundary>
              <AuthGate>
                <App />
              </AuthGate>
            </ErrorBoundary>
          </ConfirmProvider>
        </ToastProvider>
      </RouterProvider>
    </QueryClientProvider>
  </StrictMode>
);

// THE FIRST PAINT WAITS FOR THE READER'S OWN CATALOGUE, and that is what makes the split
// in `lib/i18n` invisible. `localeStore` resolves the pre-session language synchronously
// at module load — `localStorage` first, then `navigator.language` — so which catalogue is
// wanted is decidable before anything renders. A Spanish reader pays a microtask; an
// English one pays the one round trip that would otherwise have shown a Spanish frame.
// It never rejects, so there is no path where this leaves the page unrendered.
void ensureCatalogue(localeStore.getSnapshot()).then(() => {
  createRoot(document.getElementById("root")!).render(tree);
});
