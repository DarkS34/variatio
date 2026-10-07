import { describe, expect, it } from "vitest";

import { featureAccessOf } from "./types";

describe("featureAccessOf", () => {
  it("reads the mode and the list the server sends", () => {
    const payload = {
      features: {
        evaluation: { mode: "all" as const, accounts: [] },
        tutor: { mode: "selected" as const, accounts: [2, 5], workspaces: ["aula"] },
      },
    };
    expect(featureAccessOf(payload, "evaluation")).toEqual({ mode: "all", accounts: [] });
    expect(featureAccessOf(payload, "tutor")).toEqual({
      mode: "selected",
      accounts: [2, 5],
      workspaces: ["aula"],
    });
  });

  it("reads a function the answer leaves out as the server's own default: off, no list", () => {
    expect(featureAccessOf({}, "tutor")).toEqual({ mode: "off", accounts: [], workspaces: [] });
    expect(featureAccessOf(null, "evaluation")).toEqual({ mode: "off", accounts: [] });
  });

  it("keeps what it can of a malformed answer", () => {
    const payload = {
      features: { tutor: { mode: "maybe", accounts: [3, "4", null, 7.5, 9], workspaces: ["a", 2] } },
    };
    expect(featureAccessOf(payload as never, "tutor")).toEqual({
      mode: "off",
      accounts: [3, 9],
      workspaces: ["a"],
    });
  });
});
