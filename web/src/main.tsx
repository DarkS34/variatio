import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// The `wdth` sheets and not `index.css`: they are the ones that publish the width axis,
// which is what lets the type scale encode a ROLE with the width of the letter rather than
// with yet another size. Of the three families only two ship a variable build — Fontsource
// publishes no @fontsource-variable/ibm-plex-mono — so the mono is the static one.
// These must be imported BEFORE ./index.css, or the @font-face rules land after the app's
// own cascade and the first paint falls back to the system stack.
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource-variable/ibm-plex-sans/wdth.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";

import { App } from "./App";
import { ToastProvider } from "./components/ui/toast";
import { AuthGate } from "./features/auth/AuthGate";
import { ApiError } from "./lib/api";
import { RouterProvider } from "./lib/router";
import "./index.css";

const queryClient = new QueryClient({
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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Inside the router — a notice may want to link somewhere — and OUTSIDE AuthGate,
          so the login and invitation screens can acknowledge an action too. */}
      <RouterProvider>
        <ToastProvider>
          <AuthGate>
            <App />
          </AuthGate>
        </ToastProvider>
      </RouterProvider>
    </QueryClientProvider>
  </StrictMode>,
);
