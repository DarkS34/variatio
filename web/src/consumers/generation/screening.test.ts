import { describe, expect, it } from "vitest";

import type { Job } from "@/lib/types";

import { refusal, stillRefused } from "./screening";

function job(over: Partial<Job>): Job {
  return {
    id: "j1",
    kind: "generate",
    workspace: "aula",
    user_id: 1,
    user_name: "ana",
    params: { instructions: "que vaya de una panadería" },
    status: "failed",
    created_at: 0,
    started_at: 0,
    finished_at: 1,
    error: "InstructionsBlocked: «que vaya de una panadería» no se pide aquí: eso corresponde a X.",
    error_code: "instructions_blocked",
    result: null,
    label: "Generar ítems",
    artifact: null,
    elapsed_ms: 1,
    ...over,
  };
}

describe("refusal", () => {
  it("reads the refused text and the sentence, without the class name", () => {
    expect(refusal(job({}))).toEqual({
      text: "que vaya de una panadería",
      reason: "«que vaya de una panadería» no se pide aquí: eso corresponde a X.",
    });
  });

  it("is nothing for any other failure, whatever the sentence says", () => {
    expect(refusal(job({ error_code: null, error: "ValueError: no han pasado la revisión" }))).toBeNull();
    expect(refusal(job({ error_code: undefined }))).toBeNull();
  });

  it("is nothing while the job is still going, and for no job at all", () => {
    expect(refusal(job({ status: "running" }))).toBeNull();
    expect(refusal(null)).toBeNull();
  });
});

describe("stillRefused", () => {
  it("locks the button while the form holds the text that was refused", () => {
    expect(stillRefused(job({}), "que vaya de una panadería")).toMatch(/no se pide aquí/);
    expect(stillRefused(job({}), "  que vaya de una panadería \n")).toMatch(/no se pide aquí/);
  });

  it("lifts the moment the text changes", () => {
    expect(stillRefused(job({}), "que vaya de una panadería grande")).toBeNull();
    expect(stillRefused(job({}), "")).toBeNull();
  });
});
