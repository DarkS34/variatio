import { describe, expect, it } from "vitest";

import type { RunView, StepView } from "@/state/runStore";

import {
  busyDocument,
  documentLoop,
  innerLoop,
  loopLabel,
  DOCUMENTS_STEP,
  PAGES_STEP,
  SEAMS_STEP,
} from "./progress";

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
      step(PAGES_STEP, { current: 5, total: 23 }),
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

describe("innerLoop", () => {
  it("draws the pages while they are being transcribed", () => {
    const view = run([
      step(DOCUMENTS_STEP, { current: 1, total: 3 }),
      step(PAGES_STEP, { current: 12, total: 23, detail: "página 12/23" }),
    ]);
    expect(innerLoop(view)).toMatchObject({ id: PAGES_STEP, current: 12, total: 23 });
  });

  // The two loops are sequential: seams start when the pages are done. Falling through to
  // the seams is what keeps the second bar from going blank for the rest of the document.
  it("falls through to the seams once the pages are done", () => {
    const view = run([
      step(DOCUMENTS_STEP, { current: 1, total: 3 }),
      step(PAGES_STEP, { status: "ok", current: 23, total: 23 }),
      step(SEAMS_STEP, { current: 4, total: 22, detail: "costura 4→5" }),
    ]);
    expect(innerLoop(view)).toMatchObject({ id: SEAMS_STEP, current: 4, total: 22 });
  });

  it("takes the LAST page loop, not the first document's", () => {
    const view = run([
      step(PAGES_STEP, { status: "ok", current: 8, total: 8 }),
      step(PAGES_STEP, { current: 3, total: 40 }),
    ]);
    expect(innerLoop(view)).toMatchObject({ current: 3, total: 40 });
  });

  it("is null between documents", () => {
    const view = run([
      step(DOCUMENTS_STEP, { current: 2, total: 3 }),
      step(PAGES_STEP, { status: "ok", current: 8, total: 8 }),
    ]);
    expect(innerLoop(view)).toBeNull();
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

describe("loopLabel", () => {
  it("counts against the total when there is one", () => {
    expect(loopLabel({ id: "x", label: "", current: 3, total: 9, detail: null })).toBe("3/9");
  });

  it("counts alone when the total is unknown", () => {
    expect(loopLabel({ id: "x", label: "", current: 3, total: null, detail: null })).toBe("3");
  });
});
