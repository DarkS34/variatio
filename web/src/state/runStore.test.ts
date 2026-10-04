import { beforeAll, describe, expect, it, vi } from "vitest";

import type { Job, JobStatus, VgEvent } from "@/lib/types";

// The store reads the tab's workspace only to open a socket, which nothing here does; the
// real module reads `sessionStorage` on import, which node does not have.
vi.mock("./workspace", () => ({ activeWorkspace: () => null }));

import { pruneRuns, runStore, type RunView } from "./runStore";

beforeAll(() => {
  // Subscribers are woken once per frame; there is no frame in node, and none is needed.
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0);
    return 0;
  });
});

function job(id: string, kind: string, status: JobStatus, userId: number): Job {
  return {
    id,
    kind,
    workspace: "aula",
    user_id: userId,
    user_name: null,
    params: {},
    status,
    created_at: 0,
    started_at: null,
    finished_at: null,
    error: null,
    result: null,
    label: kind,
    artifact: null,
    elapsed_ms: null,
  } as Job;
}

let seq = 0;
function event(kind: string, body: Job): VgEvent {
  seq += 1;
  return { seq, ts: seq, job_id: body.id, kind, job: body };
}

function run(id: string, partial: Partial<RunView>): RunView {
  return {
    jobId: id,
    job: null,
    steps: [],
    overall: null,
    answer: "",
    thinking: "",
    phase: "idle",
    retry: null,
    items: [],
    repairs: [],
    retrieval: null,
    guardrail: null,
    fewShot: null,
    prompt: null,
    taggedCount: 0,
    tagged: [],
    startedAt: null,
    finishedAt: null,
    cancelling: false,
    ...partial,
  };
}

describe("the run store under a class talking to the tutor", () => {
  it("keeps a teacher's batch on screen however many turns other accounts queue", () => {
    runStore.ingest([event("job.started", job("batch", "generate", "running", 1))]);
    // A dozen students, one message each: every turn is a job of the workspace, and the
    // socket hands all of them to every browser in it.
    runStore.ingest(
      Array.from({ length: 14 }, (_, n) =>
        event("job.queued", job(`turn${n}`, "tutor_turn", "queued", 100 + n)),
      ),
    );
    const runs = runStore.getSnapshot().runs;
    expect(runs.batch?.job?.kind).toBe("generate");

    // A later progress event of the batch lands on the run it already has, job and all.
    runStore.ingest([{ seq: (seq += 1), ts: seq, job_id: "batch", kind: "build.progress", percent: 40 }]);
    expect(runStore.getSnapshot().runs.batch?.job?.kind).toBe("generate");
  });
});

describe("pruneRuns", () => {
  it("leaves a store within its size alone", () => {
    const runs = { a: run("a", { startedAt: 1 }) };
    expect(pruneRuns(runs, 2)).toBe(runs);
  });

  it("lets go of the finished runs first, the oldest of them first", () => {
    const runs = {
      live: run("live", { job: job("live", "generate", "running", 1), startedAt: 1 }),
      old: run("old", { job: job("old", "tag", "succeeded", 1), startedAt: 2, finishedAt: 3 }),
      recent: run("recent", { job: job("recent", "tag", "succeeded", 1), startedAt: 4, finishedAt: 5 }),
    };
    expect(Object.keys(pruneRuns(runs, 2)).sort()).toEqual(["live", "recent"]);
  });

  it("drops a run whose job is not known yet after the finished ones, and a live one never", () => {
    const runs = {
      live: run("live", { job: job("live", "generate", "queued", 1), startedAt: 1 }),
      blank: run("blank", { startedAt: null }),
      done: run("done", { job: job("done", "tag", "failed", 1), startedAt: 9, finishedAt: 10 }),
    };
    expect(Object.keys(pruneRuns(runs, 2)).sort()).toEqual(["blank", "live"]);
    expect(Object.keys(pruneRuns(runs, 1))).toEqual(["live"]);
    // More live runs than room keeps them all: the server's queue is what bounds those.
    expect(Object.keys(pruneRuns({ live: runs.live }, 0))).toEqual(["live"]);
  });
});
