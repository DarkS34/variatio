import { describe, expect, it } from "vitest";

import { accountsIn, groupOf, matchesAccount } from "./accounts";

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
