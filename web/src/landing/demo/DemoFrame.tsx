import "../i18n";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useLayoutEffect, useRef, useState } from "react";

import { App } from "@/App";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ConfirmProvider } from "@/components/ui/confirm";
import { Spinner } from "@/components/ui/spinner";
import { OverlayRoot } from "@/components/ui/overlay";
import { ToastProvider } from "@/components/ui/toast";
import { setTransport } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { MemoryRouterProvider } from "@/lib/router";
import { cn } from "@/lib/utils";
import { runStore } from "@/state/runStore";
import { workspaceStore } from "@/state/workspace";

import { transportFor } from "./api";
import type { World } from "./world";

/**
 * THE APPLICATION, INSIDE A FRAME OF THE DEMO'S PAGE, OVER THE DEMO'S OWN SERVER.
 *
 * The world is the page's (`DemoPage`), which also acts on it from the demo's own bar.
 *
 * It mounts the real `App` — the shell, the bar, the three steps and the door — under its
 * own query cache, a router that lives in memory, and its own toasts and confirmations, and
 * swaps three things of the client while it is on screen: the transport
 * (`lib/api.setTransport`), the run store's source (`runStore.drive`) and the tab's
 * workspace (`workspaceStore`). All three are put back when it leaves, and on `pagehide`
 * too, so a visitor who then logs in, or reloads, finds the client as it was. Nothing
 * outside keeps a live query while it is mounted: `AuthGate` answers `/demo` before the
 * session is asked for.
 *
 * THE FRAME CONTAINS THE APPLICATION. Its box carries a transform, which makes it the
 * containing block of every `fixed` thing inside it, and the full-screen overlays are
 * portalled into it (`ui/overlay.OverlayRoot`): a dialog, the concept picker and the toasts
 * cover the frame, as they cover the window in the application. The page scrolls inside.
 */
export function DemoFrame({ world, className }: { world: World; className?: string }) {
  const { t } = useT();
  const scroller = useRef<HTMLDivElement>(null);
  const [overlay, setOverlay] = useState<HTMLElement | null>(null);
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { refetchOnWindowFocus: false, retry: false, staleTime: 5_000 },
        },
      }),
  );
  const [ready, setReady] = useState(false);
  const toTop = useCallback(() => scroller.current?.scrollTo({ top: 0 }), []);

  useLayoutEffect(() => {
    // A reload while a demo was on screen skips every cleanup: the tab may still name the
    // demo's subject, which is nobody's.
    const before = workspaceStore.getSnapshot();
    const restore = () => {
      setTransport(null);
      runStore.drive(false);
      workspaceStore.set(before === world.slug ? null : before);
    };
    // StrictMode runs this effect, its cleanup and the effect again over ONE world: the
    // cleanup stopped its clock, and a stopped world answers nothing.
    world.resume();
    // The sample documents come in by themselves once the application is on screen.
    world.arrive();
    workspaceStore.set(world.slug);
    runStore.drive(true);
    setTransport(transportFor(world));
    window.addEventListener("pagehide", restore);
    // A change of the documents the application did not make — the bar's samples — is read
    // again at once, as the server's answer to the next question would be.
    const unsubscribe = world.subscribe(() => void client.invalidateQueries());
    setReady(true);
    return () => {
      unsubscribe();
      window.removeEventListener("pagehide", restore);
      restore();
      world.stop();
      client.clear();
    };
  }, [world, client]);

  return (
    <div
      role="region"
      aria-label={t("landing.demo.frame")}
      className={cn("relative overflow-hidden bg-background [transform:translateZ(0)]", className)}
    >
      <div ref={scroller} className="h-full overflow-y-auto overscroll-contain">
        {ready ? (
          <QueryClientProvider client={client}>
            <MemoryRouterProvider
              initialPath={world.options.preset === "ready" ? "/generate" : "/raw"}
              onNavigate={toTop}
            >
              <OverlayRoot.Provider value={overlay}>
                <ToastProvider>
                  <ConfirmProvider>
                    <ErrorBoundary>
                      <App />
                    </ErrorBoundary>
                  </ConfirmProvider>
                </ToastProvider>
              </OverlayRoot.Provider>
            </MemoryRouterProvider>
          </QueryClientProvider>
        ) : (
          <div className="flex h-full items-center justify-center">
            <Spinner className="size-5 text-muted-foreground" />
          </div>
        )}
      </div>
      <div ref={setOverlay} />
    </div>
  );
}
