import { describe, expect, it } from "vitest";

import { purge, slide, type WindowRow } from "./window";

interface Item {
  id: string;
  text?: string;
}

const ids = (rows: WindowRow<Item>[]) => rows.map((row) => row.id);
const leaving = (rows: WindowRow<Item>[]) => rows.filter((row) => row.leaving).map((row) => row.id);

describe("slide", () => {
  it("fills an empty window with every incoming item, none leaving", () => {
    const rows = slide<Item>([], [{ id: "c" }, { id: "b" }, { id: "a" }]);
    expect(ids(rows)).toEqual(["c", "b", "a"]);
    expect(leaving(rows)).toEqual([]);
  });

  it("keeps what fell off the end, marked leaving, after what is still live", () => {
    const first = slide<Item>([], [{ id: "c" }, { id: "b" }, { id: "a" }]);
    const rows = slide(first, [{ id: "d" }, { id: "c" }, { id: "b" }]);
    expect(ids(rows)).toEqual(["d", "c", "b", "a"]);
    expect(leaving(rows)).toEqual(["a"]);
  });

  it("keeps a row leaving while it is still absent", () => {
    const first = slide<Item>([], [{ id: "b" }, { id: "a" }]);
    const second = slide(first, [{ id: "c" }, { id: "b" }]);
    const third = slide(second, [{ id: "c" }, { id: "b" }]);
    expect(ids(third)).toEqual(["c", "b", "a"]);
    expect(leaving(third)).toEqual(["a"]);
  });

  it("keeps the leaving rows in the order they had", () => {
    const first = slide<Item>([], [{ id: "c" }, { id: "b" }, { id: "a" }]);
    const rows = slide(first, [{ id: "f" }, { id: "e" }, { id: "d" }]);
    expect(ids(rows)).toEqual(["f", "e", "d", "c", "b", "a"]);
    expect(leaving(rows)).toEqual(["c", "b", "a"]);
  });

  it("returns the same array when nothing moved, so the rows do not re-animate", () => {
    const a = { id: "a" };
    const b = { id: "b" };
    const first = slide<Item>([], [b, a]);
    expect(slide(first, [b, a])).toBe(first);
  });

  it("swaps an item edited in place without marking anything leaving", () => {
    const first = slide<Item>([], [{ id: "b", text: "old" }, { id: "a" }]);
    const rows = slide(first, [{ id: "b", text: "new" }, { id: "a" }]);
    expect(rows).not.toBe(first);
    expect(ids(rows)).toEqual(["b", "a"]);
    expect(leaving(rows)).toEqual([]);
    expect(rows[0].item.text).toBe("new");
  });
});

describe("purge", () => {
  it("drops the rows that finished leaving", () => {
    const first = slide<Item>([], [{ id: "b" }, { id: "a" }]);
    const rows = slide(first, [{ id: "c" }, { id: "b" }]);
    expect(ids(purge(rows))).toEqual(["c", "b"]);
  });

  it("returns the same array when there is nothing to drop", () => {
    const rows = slide<Item>([], [{ id: "a" }]);
    expect(purge(rows)).toBe(rows);
  });
});

describe("a feed that grows at the head", () => {
  // What the tagger drives: one decision at a time, newest first, cut to the window.
  const WINDOW = 3;
  const feed: Item[] = [];
  const arrive = (id: string) => {
    feed.unshift({ id });
    return feed.slice(0, WINDOW);
  };

  it("opens one row at the top and closes exactly one at the bottom", () => {
    let rows = slide<Item>([], arrive("a"));
    rows = slide(rows, arrive("b"));
    rows = slide(rows, arrive("c"));
    expect(ids(rows)).toEqual(["c", "b", "a"]);
    expect(leaving(rows)).toEqual([]);

    rows = slide(rows, arrive("d"));
    expect(ids(rows)).toEqual(["d", "c", "b", "a"]);
    expect(leaving(rows)).toEqual(["a"]);

    rows = slide(purge(rows), arrive("e"));
    expect(ids(rows)).toEqual(["e", "d", "c", "b"]);
    expect(leaving(rows)).toEqual(["b"]);
  });
});
