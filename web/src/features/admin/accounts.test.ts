import { describe, expect, it } from "vitest";

import { accountsIn, coveredBy, engineOptions, engineState, groupOf, matchesAccount } from "./accounts";

const account = (over: Partial<Parameters<typeof groupOf>[0]> = {}) => ({
  disabled: false,
  is_admin: false,
  evaluator_profile: null,
  ...over,
});

describe("groupOf", () => {
  it("lists an account under its profile", () => {
    expect(groupOf(account({ evaluator_profile: "teacher" }))).toBe("teachers");
    expect(groupOf(account({ evaluator_profile: "student" }))).toBe("students");
    expect(groupOf(account())).toBe("students");
  });

  it("puts an administrator before a profile, and a deactivated account before both", () => {
    expect(groupOf(account({ is_admin: true, evaluator_profile: "teacher" }))).toBe("admins");
    expect(groupOf(account({ is_admin: true, disabled: true }))).toBe("disabled");
  });
});

describe("matchesAccount", () => {
  const ana = { name: "Ana Gómez", username: "profe.ana" };

  it("finds an account by a part of its name or of its username", () => {
    expect(matchesAccount(ana, "góm")).toBe(true);
    expect(matchesAccount(ana, "profe.")).toBe(true);
    expect(matchesAccount(ana, "luis")).toBe(false);
  });

  it("ignores accents, capitals and the spaces around what was typed", () => {
    expect(matchesAccount(ana, "  GOMEZ ")).toBe(true);
  });

  it("matches every account while nothing is typed", () => {
    expect(matchesAccount(ana, "  ")).toBe(true);
  });
});

describe("accountsIn", () => {
  it("names every account in a subject, whatever its role, and none a teacher paused", () => {
    const accounts = [
      { id: 1, workspaces: [{ slug: "algebra", role: "owner" as const }] },
      { id: 2, workspaces: [{ slug: "algebra", role: "viewer" as const, disabled: false }] },
      { id: 3, workspaces: [{ slug: "algebra", role: "viewer" as const, disabled: true }] },
      { id: 4, workspaces: [{ slug: "fisica", role: "viewer" as const }] },
    ];
    expect(accountsIn(accounts, "algebra")).toEqual([1, 2]);
    expect(accountsIn(accounts, "quimica")).toEqual([]);
  });
});

describe("coveredBy", () => {
  const accounts = [
    { id: 1, workspaces: [{ slug: "algebra", role: "owner" as const }] },
    {
      id: 2,
      workspaces: [
        { slug: "fisica", role: "viewer" as const },
        { slug: "algebra", role: "viewer" as const },
      ],
    },
    { id: 3, workspaces: [{ slug: "algebra", role: "viewer" as const, disabled: true }] },
    { id: 4, workspaces: [{ slug: "quimica", role: "viewer" as const }] },
  ];

  it("names, for each account, the chosen subjects it is in, in the order chosen", () => {
    const covered = coveredBy(accounts, ["algebra", "fisica"]);
    expect(covered.get(1)).toEqual(["algebra"]);
    expect(covered.get(2)).toEqual(["algebra", "fisica"]);
  });

  it("leaves out an account whose only membership there is paused, and one in no chosen subject", () => {
    const covered = coveredBy(accounts, ["algebra", "fisica"]);
    expect(covered.has(3)).toBe(false);
    expect(covered.has(4)).toBe(false);
  });

  it("covers nobody while no subject is chosen", () => {
    expect(coveredBy(accounts, []).size).toBe(0);
  });
});

describe("engineOptions", () => {
  const engines = { default: "ollama", offered: ["ollama", "cerebras+ollama"] };

  it("offers the default first, then every engine offered by its own name", () => {
    expect(engineOptions(engines, null)).toEqual([
      { value: null, name: "ollama" },
      { value: "ollama", name: "ollama" },
      { value: "cerebras+ollama", name: "cerebras+ollama" },
    ]);
  });

  it("lists last an engine the account runs on that is no longer offered", () => {
    expect(engineOptions(engines, "vllm").map((option) => option.value)).toEqual([
      null,
      "ollama",
      "cerebras+ollama",
      "vllm",
    ]);
    expect(engineOptions(engines, "ollama")).toHaveLength(3);
  });

  it("offers the default alone when an older answer lists nothing", () => {
    expect(engineOptions({ default: "ollama", offered: undefined as unknown as string[] }, undefined)).toEqual([
      { value: null, name: "ollama" },
    ]);
  });
});

describe("engineState", () => {
  it("reads an engine nobody runs on as unused, whatever its instance", () => {
    expect(engineState({ users: 0, live: false })).toBe("unused");
    expect(engineState({ users: 0, live: true })).toBe("unused");
  });

  it("tells a live instance from one the server does not hold now", () => {
    expect(engineState({ users: 3, live: true })).toBe("live");
    expect(engineState({ users: 1, live: false })).toBe("idle");
  });
});
