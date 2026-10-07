import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

// The session's modules read the tab's storage when they load; node has none, so each gets
// an empty one in memory before anything is imported.
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

import { ToastProvider } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";
import { localeStore } from "@/lib/i18n";
import type { InvitePreview } from "@/lib/types";
import { authKeys } from "@/state/auth";

import { AcceptInvite } from "./AcceptInvite";

const CLASS_LINK: InvitePreview = {
  kind: "class",
  role: "viewer",
  workspace: "Programación I",
  expires_at: "2026-11-05T10:00:00+00:00",
  profile: "student",
  inviter: "Ana Pérez",
  paused: false,
};

const SARA = { user: { username: "alumna.sara" }, role: null, workspaces: [], active_workspace: null };

beforeAll(() => localeStore.adopt("es"));

/** The screen as it first draws, with the link read and the session known — or refused. */
function markup(preview: InvitePreview, session: object | null) {
  const client = new QueryClient();
  client.setQueryData(["auth", "invite", "tok"], preview);
  if (session) client.setQueryData(authKeys.me, session);
  else {
    // A refused session stays refused while the screen mounts, as the gate's first answer does.
    client.setQueryDefaults(authKeys.me, { retryOnMount: false });
    client
      .getQueryCache()
      .build(client, { queryKey: authKeys.me })
      .setState({ status: "error", error: new ApiError("No hay sesión", 401), fetchStatus: "idle" });
  }
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client },
      createElement(ToastProvider, null, createElement(AcceptInvite, { token: "tok" })),
    ),
  );
}

describe("AcceptInvite", () => {
  it("offers an open session to join, says who invites, and offers the way out", () => {
    const html = markup(CLASS_LINK, SARA);
    expect(html).toContain("Entrar en «Programación I» como alumna.sara");
    expect(html).toContain("Te invita Ana Pérez a «Programación I» como alumno.");
    expect(html).toContain("Unirme");
    expect(html).toContain("No soy alumna.sara — salir");
    expect(html).not.toContain("Crear la cuenta");
  });

  it("offers no session both ways in: a new account, or the one already held", () => {
    const html = markup(CLASS_LINK, null);
    expect(html).toContain("Crear mi cuenta");
    expect(html).toContain("Ya tengo cuenta");
    expect(html).toContain("Crear la cuenta");
    expect(html).not.toContain("Unirme");
  });

  it("says a paused link is paused and lets nothing through it", () => {
    const html = markup({ ...CLASS_LINK, paused: true }, null);
    expect(html).toContain("Este enlace está en pausa");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Crear la cuenta/);
  });

  it("gives an invitation with no subject nothing to join", () => {
    const html = markup({ ...CLASS_LINK, kind: "personal", workspace: null }, SARA);
    expect(html).toContain("Esta invitación sirve para crear una cuenta");
    expect(html).not.toContain("Unirme");
    expect(markup({ ...CLASS_LINK, kind: "personal", workspace: null }, null)).not.toContain("Ya tengo cuenta");
  });
});
