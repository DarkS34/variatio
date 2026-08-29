import { translator } from "@/lib/i18n";
import { describe, expect, it } from "vitest";

import type { Job, LaneName, LaneState, Lanes, Pipeline } from "./types";
import {
  backendsOf,
  isLive,
  isQueued,
  isSplitEngine,
  ownedBy,
  pickActiveRun,
  prospectNote,
  queuedLabel,
  queuedNotice,
  readLanes,
  waitFor,
  waitOf,
  waitReason,
} from "./queue";

const ES = translator("es");

function lane(partial: Partial<LaneState> = {}): LaneState {
  return { busy: false, mine: false, label: null, queued: 0, ahead: null, ...partial };
}

function lanes(local: Partial<LaneState> = {}, remote: Partial<LaneState> = {}): Lanes {
  return { local: lane(local), remote: lane(remote) };
}

function job(partial: Partial<Job> = {}): Job {
  return {
    id: "abc",
    kind: "build_kg",
    workspace: "default",
    user_id: null,
    user_name: null,
    params: {},
    status: "queued",
    created_at: 0,
    started_at: null,
    finished_at: null,
    error: null,
    result: null,
    label: "Construir el grafo de conocimiento",
    artifact: "knowledge_graph",
    elapsed_ms: null,
    ...partial,
  };
}

describe("readLanes", () => {
  it("is null against an API that does not split the queue", () => {
    expect(readLanes(undefined)).toBeNull();
    expect(readLanes({} as Pipeline)).toBeNull();
    expect(readLanes({ lanes: { local: lane() } } as unknown as Pipeline)).toBeNull();
  });

  it("fills in what a partial lane leaves out rather than trusting it", () => {
    const read = readLanes({
      lanes: { local: { busy: true }, remote: {} },
    } as unknown as Pipeline);
    expect(read).toEqual({
      local: { busy: true, mine: false, label: null, queued: 0, ahead: null },
      remote: { busy: false, mine: false, label: null, queued: 0, ahead: null },
    });
  });
});

describe("backendsOf", () => {
  it("tells «the API did not say» from «this job reserves nothing»", () => {
    expect(backendsOf(job())).toBeNull();
    expect(backendsOf(job({ backends: [] }))).toEqual([]);
    expect(backendsOf(job({ backends: ["remote"] }))).toEqual(["remote"]);
  });

  it("drops a lane name it does not know", () => {
    expect(backendsOf(job({ backends: ["local", "gpu2"] as LaneName[] }))).toEqual(["local"]);
  });
});

describe("waitFor", () => {
  it("counts the running job as one ahead", () => {
    expect(waitFor(lanes({ busy: true }), ["local"])).toEqual({
      lane: "local",
      ahead: 1,
      label: null,
    });
  });

  it("adds the jobs already queued in that lane", () => {
    expect(waitFor(lanes({ busy: true, queued: 2, label: "Generar ítems" }), ["local"])).toEqual({
      lane: "local",
      ahead: 3,
      label: "Generar ítems",
    });
  });

  // The complaint this module exists for: the other half being busy is not a wait.
  it("is null when MY lane is free and the other one is not", () => {
    expect(waitFor(lanes({}, { busy: true, queued: 4 }), ["local"])).toBeNull();
  });

  it("reports the slower lane of a job that reserves both", () => {
    const wait = waitFor(lanes({ busy: true }, { busy: true, queued: 2 }), ["local", "remote"]);
    expect(wait).toEqual({ lane: "remote", ahead: 3, label: null });
  });

  it("is null with no lanes and null with no backends", () => {
    expect(waitFor(null, ["local"])).toBeNull();
    expect(waitFor(lanes({ busy: true }), null)).toBeNull();
    expect(waitFor(lanes({ busy: true }), [])).toBeNull();
  });

  it("takes the job's own place over the tail of the queue", () => {
    expect(waitFor(lanes({ busy: true, queued: 5 }), ["local"], 1)).toEqual({
      lane: "local",
      ahead: 1,
      label: null,
    });
  });

  // A position travels once with the job; `ahead` is recomputed on every poll, so it is
  // the one that shrinks as the queue drains under a job that is still waiting.
  it("believes the server's own count over a position that has gone stale", () => {
    expect(waitFor(lanes({ busy: true, queued: 1, ahead: 1 }), ["local"], 4)).toEqual({
      lane: "local",
      ahead: 1,
      label: null,
    });
  });

  it("is null once the server says nothing is ahead any more", () => {
    expect(waitFor(lanes({ busy: false, queued: 1, ahead: 0 }), ["local"], 3)).toBeNull();
  });
});

describe("isQueued", () => {
  it("believes the position over the status", () => {
    expect(isQueued(job({ status: "queued", queue_position: 0 }))).toBe(false);
    expect(isQueued(job({ status: "running", queue_position: 2 }))).toBe(true);
  });

  it("falls back to the status when there is no position", () => {
    expect(isQueued(job({ status: "queued" }))).toBe(true);
    expect(isQueued(job({ status: "running" }))).toBe(false);
    expect(isQueued(null)).toBe(false);
  });
});

describe("isLive", () => {
  it("counts a job that is waiting its turn, not only one that is working", () => {
    expect(isLive(job({ status: "queued" }))).toBe(true);
    expect(isLive(job({ status: "running" }))).toBe(true);
  });

  it("is false for anything that is over, and for no job at all", () => {
    expect(isLive(job({ status: "succeeded" }))).toBe(false);
    expect(isLive(job({ status: "failed" }))).toBe(false);
    expect(isLive(job({ status: "cancelled" }))).toBe(false);
    expect(isLive(null)).toBe(false);
    expect(isLive(undefined)).toBe(false);
  });
});

describe("waitOf", () => {
  it("is null for a job that started at once", () => {
    expect(waitOf(job({ queue_position: 0 }), lanes({ busy: true }))).toBeNull();
  });

  it("is null when the lane it reserves is free, however busy the other is", () => {
    const busyRemote = lanes({}, { busy: true, queued: 3 });
    expect(waitOf(job({ backends: ["local"], queue_position: 1 }), busyRemote)).toBeNull();
  });

  it("still counts the queue when the API names no lane", () => {
    expect(waitOf(job({ queue_position: 3 }), null)).toEqual({
      lane: null,
      ahead: 2,
      label: null,
    });
  });
});

describe("what the button and the notice say", () => {
  it("labels the wait without ever naming a duration", () => {
    expect(queuedLabel({ lane: "local", ahead: 2, label: null }, ES)).toBe("En cola (2 por delante)");
    expect(queuedLabel({ lane: "local", ahead: 0, label: null }, ES)).toBe("En cola");
    expect(queuedLabel(null, ES)).toBe("En cola");
  });

  it("names the half of the engine only when there are two", () => {
    const wait = { lane: "remote" as const, ahead: 1, label: "Generar ítems" };
    expect(waitReason(wait, true, ES)).toBe(
      "Está ocupado el motor remoto con «Generar ítems»: 1 trabajo por delante.",
    );
    expect(waitReason(wait, false, ES)).toBe(
      "Está ocupado el motor con «Generar ítems»: 1 trabajo por delante.",
    );
  });

  it("says nothing at all when the job starts instead of waiting", () => {
    expect(queuedNotice(job({ queue_position: 0 }), lanes({ busy: true }), false, ES)).toBeNull();
  });

  it("names the job it is about, so the notice is not «operación completada»", () => {
    const notice = queuedNotice(
      job({ backends: ["local"], queue_position: 1 }),
      lanes({ busy: true, label: "Generar ítems" }),
      true,
      ES,
    );
    expect(notice).toEqual({
      title: "En cola: Construir el grafo de conocimiento",
      description: "Está ocupado el motor local con «Generar ítems»: 1 trabajo por delante.",
    });
  });
});

describe("prospectNote", () => {
  it("keeps the flat prediction against an API that does not split the queue", () => {
    expect(prospectNote(null, false, 2, ES)).toBe(" Se pondrá en cola: 2 trabajos por delante.");
    expect(prospectNote(null, false, 0, ES)).toBeNull();
  });

  it("predicts the wait when there is only one engine to wait for", () => {
    expect(prospectNote(lanes({ busy: true, queued: 1 }), false, 2, ES)).toBe(
      " Se pondrá en cola: 2 trabajos por delante.",
    );
    expect(prospectNote(lanes(), false, 0, ES)).toBeNull();
  });

  // With two lanes the job's own is not known until the server assigns it, so the note
  // reports the machine and states the condition instead of promising a wait.
  it("reports rather than promises when there are two engines", () => {
    expect(prospectNote(lanes({}, { busy: true, label: "Generar ítems" }), true, 1, ES)).toBe(
      " Ahora mismo el motor remoto está ocupado con «Generar ítems»; este trabajo solo" +
        " espera por el motor que necesite.",
    );
  });

  // The complaint, in the one place a person reads before pressing: a busy remote engine
  // must not turn into «se pondrá en cola» over a build that may well be local.
  it("never promises a wait it cannot know about", () => {
    const note = prospectNote(lanes({}, { busy: true }), true, 1, ES);
    expect(note).not.toContain("Se pondrá en cola");
    expect(prospectNote(lanes(), true, 0, ES)).toBeNull();
  });
});

describe("isSplitEngine", () => {
  it("reads the composite engine's own name", () => {
    expect(isSplitEngine("cerebras+ollama")).toBe(true);
    expect(isSplitEngine("ollama")).toBe(false);
    expect(isSplitEngine(undefined)).toBe(false);
  });
});

describe("pickActiveRun", () => {
  const run = (status: Job["status"] | null, startedAt: number | null) => ({
    job: status ? { status } : null,
    startedAt,
  });

  it("is null with nothing in the store", () => {
    expect(pickActiveRun({}, null)).toBeNull();
  });

  it("keeps the run this tab launched while it is still alive", () => {
    const runs = { mine: run("queued", 1), other: run("running", 9) };
    expect(pickActiveRun(runs, "mine")).toBe(runs.mine);
  });

  // Two lanes mean two live jobs, and `currentJobId` is only the last event heard.
  it("prefers the newest live run once the launched one has finished", () => {
    const runs = { mine: run("succeeded", 10), other: run("running", 2) };
    expect(pickActiveRun(runs, "mine")).toBe(runs.other);
  });

  it("falls back to the most recent finished run rather than an empty panel", () => {
    const runs = { old: run("succeeded", 1), recent: run("failed", 5) };
    expect(pickActiveRun(runs, null)).toBe(runs.recent);
  });
});

describe("ownedBy", () => {
  const job = (user_id: number | null) => ({ user_id }) as Job;

  it("matches the author and rejects everybody else", () => {
    expect(ownedBy(job(3), 3)).toBe(true);
    expect(ownedBy(job(3), 4)).toBe(false);
  });

  // Failing open is the point: hiding a run is the same failure this criterion exists
  // to remove, so an unattributable job shows to everyone rather than to nobody.
  it("fails open when either side is unknown", () => {
    expect(ownedBy(job(null), 3)).toBe(true);
    expect(ownedBy({} as Job, 3)).toBe(true);
    expect(ownedBy(job(3), null)).toBe(true);
    expect(ownedBy(job(3), undefined)).toBe(true);
  });

  it("is false with no job at all", () => {
    expect(ownedBy(null, 3)).toBe(false);
    expect(ownedBy(undefined, null)).toBe(false);
  });
});
