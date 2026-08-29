import { describe, expect, it } from "vitest";

import { behind, purge, step, type WindowRow } from "./window";

interface Item {
  id: string;
  text?: string;
}

const LIMIT = 3;

const ids = (rows: WindowRow<Item>[]) => rows.map((row) => row.id);
const leaving = (rows: WindowRow<Item>[]) => rows.filter((row) => row.leaving).map((row) => row.id);
const items = (...names: string[]): Item[] => names.map((id) => ({ id }));

describe("step", () => {
  it("fills an empty window with every incoming item, none leaving", () => {
    const rows = step<Item>([], items("c", "b", "a"), LIMIT);
    expect(ids(rows)).toEqual(["c", "b", "a"]);
    expect(leaving(rows)).toEqual([]);
  });

  it("admits exactly one row however many the source brings at once", () => {
    const first = step<Item>([], items("c", "b", "a"), LIMIT);
    const burst = items("f", "e", "d");

    const second = step(first, burst, LIMIT);
    expect(ids(second)).toEqual(["d", "c", "b", "a"]);
    expect(leaving(second)).toEqual(["a"]);

    const third = step(purge(second), burst, LIMIT);
    expect(ids(third)).toEqual(["e", "d", "c", "b"]);
    expect(leaving(third)).toEqual(["b"]);

    const fourth = step(purge(third), burst, LIMIT);
    expect(ids(fourth)).toEqual(["f", "e", "d", "c"]);
    expect(leaving(fourth)).toEqual(["c"]);
  });

  it("lets the oldest of a burst in first, so what is on top stays the newest", () => {
    let rows = step<Item>([], items("a"), LIMIT);
    const burst = items("d", "c", "b", "a");
    for (let turn = 0; turn < 3; turn += 1) rows = step(purge(rows), burst, LIMIT);
    expect(ids(purge(rows))).toEqual(["d", "c", "b"]);
  });

  it("keeps a row the source no longer lists until something pushes it out", () => {
    const first = step<Item>([], items("c", "b", "a"), LIMIT);
    // The source's own page has moved on: none of what is on screen is in it any more.
    const rows = step(first, items("z"), LIMIT);
    expect(ids(rows)).toEqual(["z", "c", "b", "a"]);
    expect(leaving(rows)).toEqual(["a"]);
  });

  it("returns the same array when nothing moved, so the rows do not re-animate", () => {
    // The same objects, which is what a poll brings back while nothing has changed.
    const same = items("b", "a");
    const first = step<Item>([], same, LIMIT);
    expect(step(first, same, LIMIT)).toBe(first);
  });

  it("swaps an item edited in place without marking anything leaving", () => {
    const first = step<Item>([], [{ id: "b", text: "old" }, { id: "a" }], LIMIT);
    const rows = step(first, [{ id: "b", text: "new" }, { id: "a" }], LIMIT);
    expect(rows).not.toBe(first);
    expect(ids(rows)).toEqual(["b", "a"]);
    expect(leaving(rows)).toEqual([]);
    expect(rows[0].item.text).toBe("new");
  });

  it("ignores what falls outside the window's own limit", () => {
    const rows = step<Item>([], items("e", "d", "c", "b", "a"), LIMIT);
    expect(ids(rows)).toEqual(["e", "d", "c"]);
  });
});

describe("behind", () => {
  it("is true while the source holds something the window has not got", () => {
    const rows = step<Item>([], items("a"), LIMIT);
    expect(behind(rows, items("c", "b", "a"), LIMIT)).toBe(true);
  });

  it("is false once the window holds what the source shows", () => {
    const rows = step<Item>([], items("c", "b", "a"), LIMIT);
    expect(behind(rows, items("c", "b", "a"), LIMIT)).toBe(false);
  });

  it("is false for what the source lists beyond the limit", () => {
    const rows = step<Item>([], items("e", "d", "c", "b", "a"), LIMIT);
    expect(behind(rows, items("e", "d", "c", "b", "a"), LIMIT)).toBe(false);
  });

  it("counts an empty window as behind whatever there is", () => {
    expect(behind<Item>([], items("a"), LIMIT)).toBe(true);
    expect(behind<Item>([], [], LIMIT)).toBe(false);
  });
});

describe("purge", () => {
  it("drops the rows that finished leaving", () => {
    const first = step<Item>([], items("b", "a"), LIMIT);
    const rows = step(first, items("c", "b", "a"), LIMIT);
    expect(ids(purge(rows))).toEqual(["c", "b", "a"]);
  });

  it("returns the same array when there is nothing to drop", () => {
    const rows = step<Item>([], items("a"), LIMIT);
    expect(purge(rows)).toBe(rows);
  });
});

describe("a feed that grows at the head", () => {
  // What the tagger drives: one decision at a time, newest first, cut to the window.
  const feed: Item[] = [];
  const arrive = (id: string) => {
    feed.unshift({ id });
    return feed.slice(0, LIMIT);
  };

  it("opens one row at the top and closes exactly one at the bottom", () => {
    let rows = step<Item>([], arrive("a"), LIMIT);
    rows = step(rows, arrive("b"), LIMIT);
    rows = step(rows, arrive("c"), LIMIT);
    expect(ids(rows)).toEqual(["c", "b", "a"]);
    expect(leaving(rows)).toEqual([]);

    rows = step(rows, arrive("d"), LIMIT);
    expect(ids(rows)).toEqual(["d", "c", "b", "a"]);
    expect(leaving(rows)).toEqual(["a"]);

    rows = step(purge(rows), arrive("e"), LIMIT);
    expect(ids(rows)).toEqual(["e", "d", "c", "b"]);
    expect(leaving(rows)).toEqual(["b"]);
  });
});
