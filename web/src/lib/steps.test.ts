import { describe, expect, it } from "vitest";

import { STEPS, currentStepPath, nextStepOf, stepBusy, stepStates } from "./steps";
import type { ArtifactStatus, Job, StageState } from "./types";

const stage = (artifact: string, status: ArtifactStatus): StageState =>
  ({ artifact, status, stale_because: [] }) as unknown as StageState;

const chain = (...statuses: ArtifactStatus[]) =>
  [
    stage("exemplars_profile", statuses[0]),
    stage("knowledge_graph", statuses[1]),
    stage("exemplars_bank", statuses[2]),
  ] as StageState[];

describe("stepStates", () => {
  it("marks exactly one step as the next move", () => {
    // What makes a path obvious is ONE next move, not a list of things outstanding.
    const states = stepStates(chain("missing", "missing", "missing"), true);
    expect(states.filter((s) => s === "now")).toHaveLength(1);
    expect(states).toEqual(["done", "now", "later", "later"]);
  });

  it("puts the first step in play while an origin has no documents", () => {
    expect(stepStates(chain("approved", "approved", "approved"), false)[0]).toBe("now");
  });

  it("only an approved stage counts as done", () => {
    // Built is not approved: until somebody closes it, the step stays open.
    const states = stepStates(chain("draft", "missing", "missing"), true);
    expect(states[1]).toBe("now");
  });

  it("a stale stage stops being done, and the path goes back to it", () => {
    // And the one BEHIND it stays marked done, which is the truth: it is approved. The path
    // sends you back to the stale one without un-doing what you did close.
    const states = stepStates(chain("approved", "stale", "approved"), true);
    expect(states).toEqual(["done", "done", "now", "done"]);
  });

  it("leaves nothing in play once the whole path is walked", () => {
    const states = stepStates(chain("approved", "approved", "approved"), true);
    expect(states.every((s) => s === "done")).toBe(true);
  });
});

describe("currentStepPath", () => {
  it("answers with the step that is next", () => {
    expect(currentStepPath(chain("approved", "missing", "missing"), true)).toBe("/prepare/graph");
  });

  it("answers with the first step when there is nothing uploaded", () => {
    expect(currentStepPath(chain("missing", "missing", "missing"), false)).toBe("/raw");
  });

  it("answers with generation once everything is approved", () => {
    // It is what everything before it was for; ending at the last step would send somebody
    // back to a screen they have already finished.
    expect(currentStepPath(chain("approved", "approved", "approved"), true)).toBe("/generate");
  });

  it("only ever answers a path the bar itself draws", () => {
    const paths = STEPS.map((s) => s.path) as string[];
    expect(paths).toContain(currentStepPath(chain("approved", "missing", "missing"), true));
  });
});

describe("the order of the path", () => {
  it("is the raw material, then review.ARTIFACTS", () => {
    // The profile comes before the syllabus because closing the syllabus needs an APPROVED
    // profile: starting at the syllabus is starting at a step you cannot finish.
    expect(STEPS.map((s) => s.artifact)).toEqual([
      null,
      "exemplars_profile",
      "knowledge_graph",
      "exemplars_bank",
    ]);
  });
});

describe("nextStepOf", () => {
  it("leads the raw material to the first stage, numbered", () => {
    // The step with no artifact offers the same "Continuar" as the rest, from the same list.
    expect(nextStepOf(null)).toEqual({
      path: "/prepare/profile",
      number: "2",
      labelKey: "nav.step.profile",
    });
  });

  it("leads the last stage to generation, unnumbered", () => {
    expect(nextStepOf("exemplars_bank")).toEqual({
      path: "/generate",
      number: null,
      labelKey: "nav.create",
    });
  });
});

describe("stepBusy", () => {
  const job = (over: Partial<Job>): Job =>
    ({ kind: "build_kg", artifact: "knowledge_graph", status: "running", ...over }) as Job;

  it("spins a stage that is building and not queued", () => {
    const busy = stepBusy(chain("approved", "building", "missing"), [job({})]);
    expect(busy).toEqual([false, false, true, false]);
  });

  it("does not spin over a build still waiting in the queue", () => {
    // A queued job is not a running one, and the wheel claims something is happening.
    const busy = stepBusy(chain("approved", "building", "missing"), [
      job({ status: "queued", queue_position: 2 }),
    ]);
    expect(busy[2]).toBe(false);
  });

  it("believes the pipeline when the stream knows no job for the artifact", () => {
    expect(stepBusy(chain("approved", "building", "missing"), [])[2]).toBe(true);
  });

  it("spins step 1 while the documents are being read, and only then", () => {
    const reading = job({ kind: "transcribe", artifact: null, status: "running" });
    expect(stepBusy(chain("missing", "missing", "missing"), [reading])[0]).toBe(true);
    const queued = job({ kind: "transcribe", artifact: null, status: "queued", queue_position: 1 });
    expect(stepBusy(chain("missing", "missing", "missing"), [queued])[0]).toBe(false);
  });
});
