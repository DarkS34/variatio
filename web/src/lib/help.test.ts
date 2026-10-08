import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

// The session's modules read the tab's storage when they load; node has none.
vi.hoisted(() => {
  const memory = (): Storage => {
    const held = new Map<string, string>();
    return {
      get length() {
        return held.size;
      },
      clear: () => held.clear(),
      getItem: (key) => held.get(key) ?? null,
      key: (index) => [...held.keys()][index] ?? null,
      removeItem: (key) => void held.delete(key),
      setItem: (key, value) => void held.set(key, String(value)),
    };
  };
  globalThis.sessionStorage ??= memory();
  globalThis.localStorage ??= memory();
});

import { GuideLink } from "@/components/GuideLink";

import { HELP_HIDDEN, isHelpPath } from "./help";

describe("the guide and the tutorial, hidden", () => {
  it("are hidden", () => {
    // The user's decision of 2026-10-07: no entry, no link, no route.
    expect(HELP_HIDDEN).toBe(true);
  });

  it("close every path of either, and nothing else", () => {
    for (const path of ["/guide", "/guide/raw", "/guide/student-start", "/tutorial", "/tutorial/2"]) {
      expect(isHelpPath(path)).toBe(true);
    }
    for (const path of ["/", "/raw", "/prepare/bank", "/guidelines", "/tutor", "/account"]) {
      expect(isHelpPath(path)).toBe(false);
    }
  });

  it("leave no «Leer en la guía» under a title", () => {
    const markup = renderToStaticMarkup(
      createElement(
        QueryClientProvider,
        { client: new QueryClient() },
        createElement(GuideLink, { slug: "bank" }),
      ),
    );
    expect(markup).toBe("");
  });
});
