import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
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
      <RouterProvider>
        <AuthGate>
          <App />
        </AuthGate>
      </RouterProvider>
    </QueryClientProvider>
  </StrictMode>,
);
