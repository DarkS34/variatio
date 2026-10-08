import { describe, expect, it } from "vitest";

import {
  STEPS,
  STUDENT_HIDDEN,
  SYLLABUS,
  USES,
  currentStepPath,
  nextStepOf,
  stepBusy,
  stepNumberOf,
  stepStates,
  studentLandingPath,
  usesFor,
} from "./steps";
import { featuresOf, type ArtifactStatus, type Job, type StageState } from "./types";

const stage = (artifact: string, status: ArtifactStatus): StageState =>
  ({ artifact, status, stale_because: [] }) as unknown as StageState;

// In `server/approvals.ARTIFACTS` order: the syllabus, the types of exercise, the bank.
const chain = (...statuses: ArtifactStatus[]) =>
  [
    stage("knowledge_graph", statuses[0]),
    stage("exemplars_profile", statuses[1]),
    stage("exemplars_bank", statuses[2]),
  ] as StageState[];

describe("stepStates", () => {
  it("marks exactly one step as the next move", () => {
    // What makes a path obvious is ONE next move, not a list of things outstanding.
    const states = stepStates(chain("missing", "missing", "missing"), true);
    expect(states.filter((s) => s === "now")).toHaveLength(1);
    expect(states).toEqual(["done", "now", "later"]);
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
    // And a step that is closed stays marked done, which is the truth: it is approved. The
    // path sends you back to the stale one without un-doing what you did close.
    const states = stepStates(chain("stale", "approved", "approved"), true);
    expect(states).toEqual(["done", "now", "done"]);
  });

  it("the bank's step is done only with its two parts closed", () => {
    // The types of exercise and the bank are one step: a bank closed over types reopened
    // since is not a finished step.
    expect(stepStates(chain("approved", "draft", "approved"), true)[2]).toBe("now");
    expect(stepStates(chain("approved", "approved", "draft"), true)[2]).toBe("now");
    expect(stepStates(chain("approved", "approved", "approved"), true)[2]).toBe("done");
  });

  it("leaves nothing in play once the whole path is walked", () => {
    const states = stepStates(chain("approved", "approved", "approved"), true);
    expect(states.every((s) => s === "done")).toBe(true);
  });
});

describe("currentStepPath", () => {
  it("answers with the step that is next", () => {
    expect(currentStepPath(chain("missing", "missing", "missing"), true)).toBe("/prepare/graph");
    expect(currentStepPath(chain("approved", "missing", "missing"), true)).toBe("/prepare/bank");
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
  it("is the raw material, then approvals.ARTIFACTS, the types and the bank as one step", () => {
    // The syllabus comes before the bank because the bank is tagged with it; the types of
    // exercise are the first part of the bank's step (2026-10-08).
    expect(STEPS.map((s) => s.artifact)).toEqual([null, "knowledge_graph", "exemplars_bank"]);
    expect(STEPS.map((s) => s.artifacts)).toEqual([
      [],
      ["knowledge_graph"],
      ["exemplars_profile", "exemplars_bank"],
    ]);
  });

  it("numbers the types of exercise as the bank's step", () => {
    expect(stepNumberOf("knowledge_graph")).toBe("2");
    expect(stepNumberOf("exemplars_profile")).toBe("3");
    expect(stepNumberOf("exemplars_bank")).toBe("3");
  });
});

describe("nextStepOf", () => {
  it("leads the raw material to the first stage, numbered", () => {
    // The step with no artifact offers the same "Continuar" as the rest, from the same list.
    expect(nextStepOf(null)).toEqual({
      path: "/prepare/graph",
      number: "2",
      labelKey: "nav.step.graph",
    });
    expect(nextStepOf("knowledge_graph")).toEqual({
      path: "/prepare/bank",
      number: "3",
      labelKey: "nav.step.bank",
    });
  });

  it("leads the last stage to generation, unnumbered", () => {
    expect(nextStepOf("exemplars_bank")).toEqual({
      path: "/generate",
      number: null,
      labelKey: "nav.create",
    });
    expect(nextStepOf("exemplars_profile")).toEqual(nextStepOf("exemplars_bank"));
  });
});

describe("stepBusy", () => {
  const job = (over: Partial<Job>): Job =>
    ({ kind: "build_kg", artifact: "knowledge_graph", status: "running", ...over }) as Job;

  it("spins a stage that is building and not queued", () => {
    const busy = stepBusy(chain("building", "missing", "missing"), [job({})]);
    expect(busy).toEqual([false, true, false]);
  });

  it("does not spin over a build still waiting in the queue", () => {
    // A queued job is not a running one, and the wheel claims something is happening.
    const busy = stepBusy(chain("building", "missing", "missing"), [
      job({ status: "queued", queue_position: 2 }),
    ]);
    expect(busy[1]).toBe(false);
  });

  it("believes the pipeline when the stream knows no job for the artifact", () => {
    expect(stepBusy(chain("building", "missing", "missing"), [])[1]).toBe(true);
  });

  it("spins the bank's step for either part, and for the review that opens a collection", () => {
    const types = job({ kind: "build_profile", artifact: "exemplars_profile" });
    expect(stepBusy(chain("approved", "building", "missing"), [types])[2]).toBe(true);
    // The review writes no bank, but the pipeline marks the bank as building from its start.
    const review = job({ kind: "review_taggability", artifact: null });
    expect(stepBusy(chain("approved", "approved", "building"), [review])[2]).toBe(true);
    const waiting = job({ kind: "review_taggability", artifact: null, status: "queued", queue_position: 1 });
    expect(stepBusy(chain("approved", "approved", "building"), [waiting])[2]).toBe(false);
  });

  it("spins step 1 while the documents are being read, and only then", () => {
    const reading = job({ kind: "transcribe", artifact: null, status: "running" });
    expect(stepBusy(chain("missing", "missing", "missing"), [reading])[0]).toBe(true);
    const queued = job({ kind: "transcribe", artifact: null, status: "queued", queue_position: 1 });
    expect(stepBusy(chain("missing", "missing", "missing"), [queued])[0]).toBe(false);
  });
});

describe("usesFor", () => {
  const keysOf = (evaluation: boolean, tutor: boolean) =>
    usesFor({ evaluation, tutor }).map((door) => door.key);

  it("always draws generating, the product's own door", () => {
    expect(keysOf(false, false)).toEqual(["generate"]);
  });

  it("draws a function's door only when it is open to the account", () => {
    expect(keysOf(true, false)).toEqual(["generate", "compare"]);
    expect(keysOf(false, true)).toEqual(["generate", "tutor"]);
  });

  it("keeps the order of USES with everything open", () => {
    expect(keysOf(true, true)).toEqual(USES.map((door) => door.key));
  });

  it("draws no optional door for a session that does not say", () => {
    // An API older than the bundle sends no `features`: both read as closed.
    expect(usesFor(featuresOf({})).map((door) => door.key)).toEqual(["generate"]);
    expect(
      usesFor(featuresOf({ features: { evaluation: "yes" } as never })).map((door) => door.key),
    ).toEqual(["generate"]);
  });

  it("drops generating only where the session says it is closed", () => {
    // Generating was always open: only a literal `false` (a subject's teachers closed it to
    // its students) takes its door away.
    expect(featuresOf({}).generate).toBe(true);
    expect(featuresOf({ features: { generate: false } }).generate).toBe(false);
    expect(
      usesFor(featuresOf({ features: { generate: false, tutor: true } })).map((door) => door.key),
    ).toEqual(["tutor"]);
  });
});

describe("a student's bar", () => {
  it("draws the syllabus alone of the construction, at the graph step's own path", () => {
    const graph = STEPS.find((step) => step.artifact === "knowledge_graph")!;
    expect(SYLLABUS.path).toBe(graph.path);
    expect(SYLLABUS.labelKey).toBe(graph.labelKey);
    // Not a door: the doors stay the three of USES.
    expect(USES.map((door) => door.key)).not.toContain(SYLLABUS.key);
  });

  it("hides every other step of the construction, the raw material included", () => {
    expect([...STUDENT_HIDDEN].sort()).toEqual(["/prepare/bank", "/raw"]);
    expect(STUDENT_HIDDEN).not.toContain(SYLLABUS.path);
  });
});

describe("studentLandingPath", () => {
  it("lands on generating while it is open", () => {
    expect(studentLandingPath({ evaluation: true, tutor: true })).toBe("/generate");
    expect(studentLandingPath({ evaluation: false, tutor: false })).toBe("/generate");
  });

  it("goes on to the tutor, then the syllabus, where the teachers closed generating", () => {
    expect(studentLandingPath({ evaluation: true, tutor: true, generate: false })).toBe("/tutor");
    expect(studentLandingPath({ evaluation: false, tutor: false, generate: false })).toBe(
      "/prepare/graph",
    );
  });
});
