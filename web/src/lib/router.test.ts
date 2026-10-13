import { describe, expect, it } from "vitest";

import { pathOf } from "./router";

describe("the route of an address", () => {
  it("is its path, without the query a screen reads", () => {
    expect(pathOf("/demo?start=generate")).toBe("/demo");
  });

  it("drops a fragment too", () => {
    expect(pathOf("/guide/bank#tipos")).toBe("/guide/bank");
  });

  it("is the address itself when it carries neither", () => {
    expect(pathOf("/prepare/bank")).toBe("/prepare/bank");
  });

  it("is the root for an address that is only a query", () => {
    expect(pathOf("?token=abc")).toBe("/");
  });
});
