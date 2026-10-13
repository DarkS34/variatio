import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  const memory = (): Storage => {
    const held = new Map<string, string>();
    return {
      get length() {
        return held.size;
      },
      clear: () => held.clear(),
      getItem: (key) => held.get(key) ?? null,
      key: (index) => [...held.keys()][index] ?? null,
      removeItem: (key) => void held.delete(key),
      setItem: (key, value) => void held.set(key, String(value)),
    };
  };
  globalThis.sessionStorage ??= memory();
  globalThis.localStorage ??= memory();
  globalThis.requestAnimationFrame ??= ((callback: FrameRequestCallback) =>
    setTimeout(() => callback(Date.now()), 0) as unknown as number) as typeof requestAnimationFrame;
});

import type { JobKind } from "@/lib/types";
import { runStore } from "@/state/runStore";

import { createWorld, type Preset, type World } from "./world";

const OPTIONS = {
  language: () => "es" as const,
  subjectName: () => "Lorem ipsum I",
  teacherName: () => "Docente de ejemplo",
};

/** Virtual milliseconds from queueing `kind` until every job of the world has ended. */
async function timeOf(world: World, kind: JobKind, params: Record<string, unknown> = {}): Promise<number> {
  world.submit(kind, params);
  let elapsed = 0;
  while (world.live().length > 0 && elapsed < 300_000) {
    await vi.advanceTimersByTimeAsync(10);
    elapsed += 10;
  }
  return elapsed;
}

function fresh(preset: Preset = "fresh"): World {
  const world = createWorld({ preset, ...OPTIONS });
  world.addSamples();
  return world;
}

beforeEach(() => {
  runStore.drive(true);
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

// A visitor waits seconds, not minutes (the user's request, 2026-10-12). Measured on the day:
// 1.2 s a slot's reading, 2.3 s the syllabus with its descriptions, 1.0 s the types, 1.9 s
// the whole bank's collection and 1.9 s a commission of three — from 5.1, 11.6, 3.6, 9.5 and
// 13.2 s before. The bounds leave room for the shape of a job to change, not its pace.
describe("the demo's pace", () => {
  it("reads a slot of 42 pages in under 2 s", async () => {
    expect(await timeOf(fresh(), "transcribe", { slot: "corpus" })).toBeLessThan(2_000);
  });

  it("builds the syllabus, descriptions included, in under 3.5 s", async () => {
    expect(await timeOf(fresh(), "build_kg")).toBeLessThan(3_500);
  });

  it("builds the types of exercise in under 2 s", async () => {
    expect(await timeOf(fresh(), "build_profile")).toBeLessThan(2_000);
  });

  it("collects the whole bank, its three links, in under 3.5 s", async () => {
    const world = fresh();
    await timeOf(world, "build_kg");
    world.approve("knowledge_graph");
    await timeOf(world, "build_profile");
    world.approve("exemplars_profile");
    expect(await timeOf(world, "review_taggability")).toBeLessThan(3_500);
    expect(world.stageState("exemplars_bank").status).toBe("approved");
  });

  it("writes a commission of three exercises in under 4 s", async () => {
    const params = { n: 3, concepts: ["Sit amet"], item_type: "problema", think: "low" };
    expect(await timeOf(fresh("ready"), "generate", params)).toBeLessThan(4_000);
  });
});
