import { bytes } from "@/lib/format";
import type { Key, Language, Translate as Catalogue } from "@/lib/i18n";
import { jobName } from "@/lib/names";
import type {
  AdminEngine,
  AdminJobQueue,
  CerebrasState,
  TunnelStatus,
} from "@/lib/types";

/**
 * What each part of the engine is doing, in one word and one line.
 *
 * The rows of the tab's list and the cards' badges read the same functions, so a part
 * cannot be "en reposo" on its card and something else on its row. Nothing here draws.
 */

export type ScreenKey = "general" | "local" | "remote";

/** The registry's name for the engine that sends its generative models to Cerebras. */
export const HYBRID = "cerebras+ollama";

/* What each engine is, said as the choice it is. A value the registry adds later is drawn
   by its own name until it gets a line here. */
export const ENGINE_KINDS: Record<string, { title: Key; note: Key }> = {
  ollama: { title: "eng.kind.local", note: "eng.kind.localNote" },
  [HYBRID]: { title: "eng.kind.hybrid", note: "eng.kind.hybridNote" },
};

/** settled, working, act here, failing, not there — in the palette's own terms. */
export type CellTone = "ok" | "live" | "act" | "down" | "off";

export interface BoardCell {
  key: ScreenKey;
  label: string;
  state: string;
  detail: string;
  tone: CellTone;
  /** Settings of this part changed and not saved yet. */
  pending: number;
}

type Reading = Omit<BoardCell, "pending">;
type Translate = Catalogue & { language: Language };

export function generalCell(
  engine: AdminEngine,
  jobs: AdminJobQueue | undefined,
  tr: Translate,
): Reading {
  const { t, plural } = tr;
  const kind = ENGINE_KINDS[engine.engine];
  const base = {
    key: "general" as const,
    label: t("eng.board.general"),
    state: kind ? t(kind.title) : engine.engine,
  };
  // The engine out of reach and a tunnel that could reach it: the move is on this screen,
  // so this is the cell that asks for somebody while the local one says what is failing.
  if (!engine.available && engine.tunnel.configured && !engine.tunnel.running) {
    const tunnel = tunnelState(engine.tunnel, engine.available);
    return { ...base, detail: `${t("eng.tunnel.title")}: ${t(tunnel.labelKey)}`, tone: "act" };
  }
  if (!jobs) return { ...base, detail: "", tone: "ok" };
  if (jobs.running) {
    const job = jobName(jobs.running.kind, t, jobs.running.label) || t("eng.board.working");
    return {
      ...base,
      detail: plural("eng.board.queue.behind", jobs.queued.length, { job }),
      tone: "live",
    };
  }
  const waiting =
    jobs.queued.length > 0
      ? plural("eng.board.queue.waiting", jobs.queued.length)
      : t("eng.board.queue.nobody");
  return { ...base, detail: waiting, tone: "ok" };
}

export function localCell(engine: AdminEngine, tr: Translate): Reading {
  const { t, plural } = tr;
  const base = { key: "local" as const, label: t("eng.half.local") };
  if (!engine.available) {
    return { ...base, state: t("eng.board.local.offline"), detail: t("engine.offline"), tone: "down" };
  }
  const vram = engine.running.reduce((sum, model) => sum + (model.size_vram ?? 0), 0);
  const resident =
    engine.running.length > 0
      ? plural("eng.gpu.resident", engine.running.length, { size: bytes(vram) })
      : t("eng.gpu.nothingResident");
  const missing = engine.required.filter((row) => row.state === "not_installed").length;
  if (missing > 0) {
    return { ...base, state: plural("eng.board.local.missing", missing), detail: resident, tone: "act" };
  }
  return {
    ...base,
    state: t(engine.busy ? "eng.board.working" : "eng.board.local.online"),
    detail: resident,
    tone: engine.busy ? "live" : "ok",
  };
}

export function remoteCell(engine: AdminEngine, tr: Translate): Reading {
  const { t, language } = tr;
  const base = { key: "remote" as const, label: t("eng.half.remote") };
  const cerebras = engine.cerebras;
  // Chosen in the draft and not saved: the half exists so its key can be filled in, and it
  // measures nothing until the engine is actually this one.
  if (!cerebras?.active) {
    return { ...base, state: t("eng.board.remote.draft"), detail: t("eng.board.remote.draftNote"), tone: "off" };
  }
  const state = cerebrasState(cerebras);
  const tokens = cerebras.usage.reduce((sum, entry) => sum + entry.windows.day.tokens_used, 0);
  return {
    ...base,
    state: t(state.labelKey),
    detail:
      tokens > 0
        ? t("eng.board.remote.spent", { n: tokens.toLocaleString(language) })
        : t("eng.board.remote.unspent"),
    tone: state.cell,
  };
}

/**
 * The connection to Ollama in one word, read the same by its card and by the list.
 *
 * An installation that names no tunnel host speaks to `OLLAMA_HOST` directly — Ollama on
 * this machine, or one reached over the network. That is a way of connecting and not a
 * tunnel left unconfigured: there is nothing to raise, only an engine that answers or not.
 *
 * With a tunnel named, the engine answering on the local port while this process runs no
 * ssh means the port is reached some other way — a tunnel opened by hand. That is not
 * "apagado", and offering "Conectar" would launch an ssh onto a port already taken.
 */
export function tunnelState(
  tunnel: TunnelStatus,
  available: boolean,
): {
  labelKey: Key;
  tone: "settled" | "attention" | "outline";
  direct: boolean;
  external: boolean;
} {
  const direct = !tunnel.configured;
  if (direct) {
    return available
      ? { labelKey: "tunnel.direct", tone: "settled", direct, external: false }
      : { labelKey: "tunnel.directSilent", tone: "attention", direct, external: false };
  }
  const external = available && !tunnel.running && !tunnel.wanted;
  if (external) return { labelKey: "tunnel.external", tone: "settled", direct, external };
  if (tunnel.running) return { labelKey: "tunnel.connected", tone: "settled", direct, external };
  if (tunnel.wanted) return { labelKey: "tunnel.reconnecting", tone: "attention", direct, external };
  return { labelKey: "tunnel.off", tone: "outline", direct, external };
}

/**
 * The remote half in one word.
 *
 * Only ever asked while the engine routes here, so there is no "motor inactivo" state to
 * name: with the plain `ollama` engine the whole half is gone from the tab.
 */
export function cerebrasState(cerebras: CerebrasState): {
  labelKey: Key;
  tone: "danger" | "attention" | "settled" | "outline";
  cell: CellTone;
} {
  const blocked = cerebras.usage.some(
    (entry) => entry.windows.day.requests_remaining <= 0 || entry.windows.day.tokens_remaining <= 0,
  );
  if (blocked) return { labelKey: "cere.state.exhausted", tone: "danger", cell: "down" };
  if (cerebras.inflight?.waiting_until != null)
    return { labelKey: "cere.state.waiting", tone: "attention", cell: "act" };
  if (cerebras.inflight) return { labelKey: "cere.state.running", tone: "settled", cell: "live" };
  // Routed here with no key: every call would be refused, and filling it in is the move.
  if (!cerebras.configured) return { labelKey: "cere.state.noKey", tone: "outline", cell: "act" };
  return { labelKey: "cere.state.idle", tone: "settled", cell: "ok" };
}
