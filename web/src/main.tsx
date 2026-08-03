import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { RouterProvider } from "./lib/router";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The pipeline is one user editing files on one machine: refetching on focus
      // buys nothing and would fight with unsaved editor state.
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider>
        <App />
      </RouterProvider>
    </QueryClientProvider>
  </StrictMode>,
);
