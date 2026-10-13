import { describe, expect, it } from "vitest";

import type { RunView, StepView } from "@/state/runStore";

import { busyDocument, documentLoop, DOCUMENTS_STEP, rawStepDone } from "./progress";

function step(id: string, over: Partial<StepView> = {}): StepView {
  return {
    key: `${id}#0`,
    id,
    label: id,
    status: "running",
    startedAt: 0,
    ...over,
  };
}

function run(steps: StepView[], status = "running"): RunView {
  return {
    jobId: "j",
    job: { id: "j", kind: "transcribe", status } as RunView["job"],
    steps,
    overall: null,
  } as RunView;
}

describe("documentLoop", () => {
  it("reads the outer loop and not the inner one", () => {
    const view = run([
      step(DOCUMENTS_STEP, { current: 2, total: 7, detail: "examen.pdf" }),
      step("transcribe", { current: 5, total: 23 }),
    ]);
    expect(documentLoop(view)).toMatchObject({ current: 2, total: 7, detail: "examen.pdf" });
  });

  it("is null once the loop has finished", () => {
    const view = run([step(DOCUMENTS_STEP, { status: "ok", current: 7, total: 7 })]);
    expect(documentLoop(view)).toBeNull();
  });

  it("survives a run with no steps at all", () => {
    expect(documentLoop(run([]))).toBeNull();
    expect(documentLoop(null)).toBeNull();
  });
});

describe("busyDocument", () => {
  it("names the document being rewritten right now", () => {
    const view = run([step(DOCUMENTS_STEP, { current: 2, total: 7, detail: "examen.pdf" })]);
    expect(busyDocument(view)).toBe("examen.pdf");
  });

  // Queued is not running: nothing is being written, so nothing is off limits to edit.
  it("names nothing while the job only waits its turn", () => {
    const view = run(
      [step(DOCUMENTS_STEP, { current: 0, total: 7, detail: "examen.pdf" })],
      "queued",
    );
    expect(busyDocument(view)).toBeNull();
  });

  it("names nothing once the job is over", () => {
    const view = run([step(DOCUMENTS_STEP, { detail: "examen.pdf" })], "succeeded");
    expect(busyDocument(view)).toBeNull();
  });
});

describe("whether step 1 is done", () => {
  it("is not with an origin empty, read or not", () => {
    expect(rawStepDone(false, true, false, 0)).toBe(false);
  });

  it("is not while a document of a stocked origin is unread, stale or has pages to read again", () => {
    expect(rawStepDone(true, true, false, 4)).toBe(false);
    expect(rawStepDone(true, true, false, 1)).toBe(false);
  });

  it("is not while the documents are being read", () => {
    expect(rawStepDone(true, true, true, 0)).toBe(false);
  });

  it("is with both origins stocked and every document read", () => {
    expect(rawStepDone(true, true, false, 0)).toBe(true);
  });

  it("keeps to the stocked origins until the readings land, so a read subject never flashes", () => {
    expect(rawStepDone(true, false, false, 0)).toBe(true);
  });
});
