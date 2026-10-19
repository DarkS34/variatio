import { describe, expect, it } from "vitest";

import {
  STEPS,
  STUDENT_HIDDEN,
  STUDENT_READS,
  SYLLABUS,
  USES,
  afterConstruction,
  currentStepPath,
  nextStepOf,
  stepBusy,
  stepNumberOf,
  stepStates,
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

  it("puts the first step in play while an origin has no documents or one is unread", () => {
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
  const all = { evaluation: false, tutor: false };

  it("answers with the step that is next", () => {
    expect(currentStepPath(chain("missing", "missing", "missing"), true, all)).toBe("/prepare/graph");
    expect(currentStepPath(chain("approved", "missing", "missing"), true, all)).toBe("/prepare/bank");
  });

  it("answers with the first step when there is nothing uploaded", () => {
    expect(currentStepPath(chain("missing", "missing", "missing"), false, all)).toBe("/raw");
  });

  it("answers with generation once everything is approved", () => {
    // It is what everything before it was for; ending at the last step would send somebody
    // back to a screen they have already finished.
    expect(currentStepPath(chain("approved", "approved", "approved"), true, all)).toBe("/generate");
  });

  it("answers with the first open door where generating is closed to the account", () => {
    const done = chain("approved", "approved", "approved");
    expect(currentStepPath(done, true, { evaluation: false, tutor: true, generate: false })).toBe(
      "/tutor",
    );
    expect(currentStepPath(done, true, { evaluation: false, tutor: false, generate: false })).toBe(
      "/prepare/graph",
    );
  });

  it("only ever answers a path the bar itself draws", () => {
    const paths = STEPS.map((s) => s.path) as string[];
    expect(paths).toContain(currentStepPath(chain("approved", "missing", "missing"), true, all));
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
  const all = { evaluation: false, tutor: false };

  it("leads the raw material to the first stage, numbered", () => {
    // The step with no artifact offers the same "Continuar" as the rest, from the same list.
    expect(nextStepOf(null, all)).toEqual({
      path: "/prepare/graph",
      number: "2",
      labelKey: "nav.step.graph",
    });
    expect(nextStepOf("knowledge_graph", all)).toEqual({
      path: "/prepare/bank",
      number: "3",
      labelKey: "nav.step.bank",
    });
  });

  it("leads the last stage to generation, unnumbered", () => {
    expect(nextStepOf("exemplars_bank", all)).toEqual({
      path: "/generate",
      number: null,
      labelKey: "nav.create",
    });
    expect(nextStepOf("exemplars_profile", all)).toEqual(nextStepOf("exemplars_bank", all));
  });

  it("leads the last stage to the first open door where generating is closed", () => {
    expect(nextStepOf("exemplars_bank", { evaluation: false, tutor: false, generate: false, chat: true })).toEqual({
      path: "/chat",
      number: null,
      labelKey: "nav.chat",
    });
    expect(nextStepOf("exemplars_bank", { evaluation: false, tutor: false, generate: false })).toEqual({
      path: "/prepare/graph",
      number: null,
      labelKey: "nav.step.graph",
    });
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
    expect(usesFor({ evaluation: true, tutor: true, chat: true }).map((door) => door.key)).toEqual(
      USES.map((door) => door.key),
    );
  });

  it("draws the chat only where the session says it is open", () => {
    // A subject opens it to its students and it starts closed; an older API never sends it.
    expect(featuresOf({}).chat).toBe(false);
    expect(featuresOf({ features: { chat: true } }).chat).toBe(true);
    expect(keysOf(true, true)).not.toContain("chat");
    expect(usesFor(featuresOf({ features: { chat: true } })).map((door) => door.key)).toEqual([
      "generate",
      "chat",
    ]);
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

  it("keeps the class page open unless the session closes it, as the demo's does", () => {
    expect(featuresOf({}).class).toBe(true);
    expect(featuresOf({ features: { class: false } }).class).toBe(false);
    // It is no door of the bar either way.
    expect(usesFor(featuresOf({ features: { class: false } })).map((door) => door.key)).toEqual(["generate"]);
  });
});

describe("a student's bar", () => {
  it("draws the syllabus and the bank of the construction, at their steps' own paths", () => {
    const graph = STEPS.find((step) => step.artifact === "knowledge_graph")!;
    const bank = STEPS.find((step) => step.artifact === "exemplars_bank")!;
    expect(STUDENT_READS.map((reading) => reading.path)).toEqual([graph.path, bank.path]);
    expect(STUDENT_READS.map((reading) => reading.labelKey)).toEqual([graph.labelKey, bank.labelKey]);
    expect(STUDENT_READS[0]).toBe(SYLLABUS);
    // Not doors.
    for (const reading of STUDENT_READS) {
      expect(USES.map((door) => door.key)).not.toContain(reading.key);
    }
  });

  it("hides the raw material, and the types' old address that leads to the bank", () => {
    expect([...STUDENT_HIDDEN].sort()).toEqual(["/prepare/profile", "/raw"]);
    for (const reading of STUDENT_READS) expect(STUDENT_HIDDEN).not.toContain(reading.path);
  });
});

describe("afterConstruction", () => {
  const path = (features: Parameters<typeof afterConstruction>[0]) => afterConstruction(features).path;

  it("leads to generating while it is open", () => {
    expect(path({ evaluation: true, tutor: true })).toBe("/generate");
    expect(path({ evaluation: false, tutor: false })).toBe("/generate");
  });

  it("goes on to the first open door in the bar's order where generating is closed", () => {
    // The user's request (2026-10-19): «la primera que esté en la lista», the bar's list.
    expect(path({ evaluation: true, tutor: true, generate: false, chat: true })).toBe("/evaluate");
    expect(path({ evaluation: false, tutor: true, generate: false, chat: true })).toBe("/tutor");
    expect(path({ evaluation: false, tutor: false, generate: false, chat: true })).toBe("/chat");
  });

  it("falls back to the syllabus, which every account sees, with no door open", () => {
    expect(afterConstruction({ evaluation: false, tutor: false, generate: false })).toEqual({
      path: SYLLABUS.path,
      labelKey: SYLLABUS.labelKey,
    });
  });

  it("follows the door the bar draws first", () => {
    const features = featuresOf({ features: { generate: false, tutor: true, chat: true } });
    expect(path(features)).toBe(usesFor(features)[0].path);
  });
});
