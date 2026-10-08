import { describe, expect, it } from "vitest";

import { readParts, type PartFacts } from "./parts";

const facts = (over: Partial<PartFacts> = {}): PartFacts => ({
  profile: "missing",
  profileHash: false,
  typesDrift: false,
  typesCurating: false,
  typesDirty: false,
  bank: "missing",
  bankStale: false,
  bankCurating: false,
  collecting: false,
  collectionFailed: false,
  graphReady: true,
  ...over,
});

describe("readParts", () => {
  it("keeps the bank closed until the types exist", () => {
    const fresh = readParts(facts());
    expect(fresh).toMatchObject({ types: "now", bank: "later", bankOpen: false, opening: "types" });
    const first = readParts(facts({ profile: "building" }));
    expect(first).toMatchObject({ types: "building", bank: "later", bankOpen: false, opening: "types" });
  });

  it("points at the bank once the types are built, and opens on the types to read them", () => {
    const built = readParts(facts({ profile: "draft", profileHash: true }));
    expect(built).toMatchObject({ types: "done", bank: "now", bankOpen: true, opening: "types" });
    expect(built.recollect).toBe(false);
  });

  it("does not point at the bank while the syllabus is open", () => {
    const open = readParts(facts({ profile: "draft", profileHash: true, graphReady: false }));
    expect(open).toMatchObject({ types: "done", bank: "later", bankOpen: true });
  });

  it("opens on the bank while it is collected, and once it is there", () => {
    const running = readParts(facts({ profile: "approved", profileHash: true, bank: "building", collecting: true }));
    expect(running).toMatchObject({ types: "done", bank: "building", collected: false, opening: "bank" });
    // Extracted and tagged is done, closed or not: closing it is the screen's way out.
    const there = readParts(facts({ profile: "approved", profileHash: true, bank: "draft" }));
    expect(there).toMatchObject({ types: "done", bank: "done", collected: true, opening: "bank" });
    const closed = readParts(facts({ profile: "approved", profileHash: true, bank: "approved" }));
    expect(closed).toMatchObject({ types: "done", bank: "done", recollect: false });
  });

  it("opens on the bank where the last collection stopped", () => {
    const stopped = readParts(facts({ profile: "approved", profileHash: true, collectionFailed: true }));
    expect(stopped).toMatchObject({ bank: "now", opening: "bank" });
  });

  it("offers the bank again when the types changed after it was collected", () => {
    const edited = readParts(facts({ profile: "draft", profileHash: true, bank: "draft" }));
    expect(edited).toMatchObject({ types: "changed", bank: "now", recollect: true });
    // An edit still in the editor counts: closing the bank would seal it with them.
    const unsaved = readParts(
      facts({ profile: "approved", profileHash: true, bank: "approved", typesDirty: true, typesCurating: true }),
    );
    expect(unsaved).toMatchObject({ types: "curating", bank: "later", recollect: true });
  });

  it("offers the bank again when it is stale", () => {
    const stale = readParts(facts({ profile: "approved", profileHash: true, bank: "stale", bankStale: true }));
    expect(stale).toMatchObject({ types: "done", bank: "now", recollect: true });
  });

  it("puts the types first when their documents changed, and still opens on the bank", () => {
    const drift = readParts(
      facts({ profile: "stale", profileHash: true, typesDrift: true, bank: "stale", bankStale: true }),
    );
    expect(drift).toMatchObject({ types: "now", bank: "later", opening: "bank" });
    // With no bank yet, the types are where the step is.
    const early = readParts(facts({ profile: "stale", profileHash: true, typesDrift: true }));
    expect(early).toMatchObject({ types: "now", opening: "types" });
  });

  it("keeps the bank open while the types are rebuilt", () => {
    const rebuild = readParts(facts({ profile: "building", profileHash: true, bank: "stale", bankStale: true }));
    expect(rebuild).toMatchObject({ types: "building", bank: "later", bankOpen: true, opening: "types" });
  });
});
