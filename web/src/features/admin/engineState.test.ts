import { describe, expect, it } from "vitest";

import { translator } from "@/lib/i18n";
import type { AdminEngine, CerebrasState, CerebrasWindow, Job, TunnelStatus } from "@/lib/types";

import { cerebrasState, generalCell, localCell, remoteCell, tunnelState } from "./engineState";

/**
 * What the tab's list says about each part of the engine.
 *
 * A cell's tone is the one thing on the tab that claims «here is where you act», so the
 * cases worth pinning are the ones where two readings disagree: an engine that answers with
 * no ssh of ours, an engine that is down while a tunnel could still reach it — red on the
 * part that fails, blue on the part where the move is — and a part that exists only in an
 * unsaved draft.
 */
const tr = { ...translator("es"), language: "es" as const };

const TUNNEL: TunnelStatus = {
  configured: true,
  host: "gpu",
  local_port: 13434,
  remote_port: 11434,
  autostart: false,
  wanted: false,
  running: false,
  pid: null,
  since: null,
  attempts: 0,
  last_error: null,
  stderr: [],
};

const ENGINE: AdminEngine = {
  engine: "ollama",
  host: "http://localhost:13434",
  available: true,
  running: [],
  installed: [],
  required: [],
  idle: { seconds: 0, threshold: 1800, poll: 60 },
  busy: false,
  contexts: [],
  pulls: [],
  tunnel: TUNNEL,
};

const WINDOW: CerebrasWindow = {
  requests_used: 0,
  requests_limit: 10,
  requests_remaining: 10,
  tokens_used: 0,
  tokens_limit: 1000,
  tokens_remaining: 1000,
  resets_in: 0,
};

const CEREBRAS: CerebrasState = {
  active: true,
  configured: true,
  routed: ["gemma-4-31b"],
  max_wait: 90,
  usage: [],
  inflight: null,
};

describe("the tunnel in one word", () => {
  it("is external, not off, when the engine answers and this process runs no ssh", () => {
    expect(tunnelState(TUNNEL, true)).toMatchObject({ labelKey: "tunnel.external", external: true });
  });

  it("is reconnecting while ssh is wanted and not alive", () => {
    const state = tunnelState({ ...TUNNEL, wanted: true }, false);
    expect(state).toMatchObject({ labelKey: "tunnel.reconnecting", tone: "attention" });
  });

  it("is off when nobody asked for it and nothing answers", () => {
    expect(tunnelState(TUNNEL, false).labelKey).toBe("tunnel.off");
  });

  it("is a direct connection, not a missing tunnel, when no host is named", () => {
    const bare = { ...TUNNEL, configured: false, host: "" };
    expect(tunnelState(bare, true)).toMatchObject({
      labelKey: "tunnel.direct",
      tone: "settled",
      direct: true,
      external: false,
    });
    expect(tunnelState(bare, false)).toMatchObject({
      labelKey: "tunnel.directSilent",
      tone: "attention",
      direct: true,
    });
  });
});

describe("the local cell", () => {
  it("is settled while the engine answers and nothing runs", () => {
    expect(localCell(ENGINE, tr).tone).toBe("ok");
  });

  it("is failing when the engine is out of reach, whatever the tunnel is doing", () => {
    expect(localCell({ ...ENGINE, available: false }, tr).tone).toBe("down");
    const retrying = { ...ENGINE, available: false, tunnel: { ...TUNNEL, wanted: true } };
    expect(localCell(retrying, tr).tone).toBe("down");
  });

  it("points at a model the configuration names and the disk lacks", () => {
    const engine: AdminEngine = {
      ...ENGINE,
      required: [{ model: "qwen3.8:27b-q8_0", asked_by: ["generate"], state: "not_installed" }],
    };
    const cell = localCell(engine, tr);
    expect(cell.tone).toBe("act");
    expect(cell.state).toBe("Falta 1 modelo");
  });
});

describe("the remote cell", () => {
  it("is not there yet while the engine is only chosen in the draft", () => {
    expect(remoteCell(ENGINE, tr).tone).toBe("off");
    expect(remoteCell({ ...ENGINE, cerebras: { ...CEREBRAS, active: false } }, tr).tone).toBe("off");
  });

  it("is failing once a daily window has nothing left", () => {
    const spent = { ...WINDOW, tokens_used: 12_000, tokens_limit: 12_000, tokens_remaining: 0 };
    const usage = [{ model: "gemma-4-31b", windows: { minute: WINDOW, day: spent }, phases: [] }];
    const cerebras = { ...CEREBRAS, usage } as CerebrasState;
    expect(cerebrasState(cerebras).cell).toBe("down");
    expect(remoteCell({ ...ENGINE, cerebras }, tr).detail).toBe("12.000 tokens en 24 h");
  });

  it("asks for the administrator while the throttle holds a call back", () => {
    const inflight = { model: "gemma-4-31b", phase: "generate", since: 0, elapsed: 1, waiting_until: 9 };
    expect(cerebrasState({ ...CEREBRAS, inflight }).cell).toBe("act");
  });

  it("asks for the key when the engine routes here without one", () => {
    expect(cerebrasState({ ...CEREBRAS, configured: false }).cell).toBe("act");
  });
});

describe("the general cell", () => {
  const job = { id: "j1", kind: "generate", label: "", workspace: "fisica", status: "running" } as Job;

  it("says which engine the installation runs", () => {
    expect(generalCell(ENGINE, { running: null, queued: [] }, tr)).toMatchObject({
      state: "Solo local",
      detail: "Cola libre",
      tone: "ok",
    });
    expect(generalCell({ ...ENGINE, engine: "cerebras+ollama" }, undefined, tr).state).toBe("Híbrido");
  });

  it("names the running job and counts who waits behind it", () => {
    const cell = generalCell(ENGINE, { running: job, queued: [{ ...job, id: "j2", queue_position: 1 }] }, tr);
    expect(cell.tone).toBe("live");
    expect(cell.detail).toBe("Generar ejercicios · 1 en espera");
  });

  it("asks for somebody when the engine is out of reach and a tunnel could reach it", () => {
    const cell = generalCell({ ...ENGINE, available: false }, { running: null, queued: [] }, tr);
    expect(cell).toMatchObject({ tone: "act", detail: "Túnel SSH: apagado" });
  });

  it("does not, when there is no tunnel to raise", () => {
    const bare = { ...ENGINE, available: false, tunnel: { ...TUNNEL, configured: false } };
    expect(generalCell(bare, { running: null, queued: [] }, tr).tone).toBe("ok");
  });
});
