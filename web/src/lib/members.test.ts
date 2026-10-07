import { describe, expect, it } from "vitest";

import { inFilter, matchesMember, studentsOf, viaKey } from "./members";
import type { Member } from "./types";

const member = (overrides: Partial<Member>): Member => ({
  user_id: 1,
  name: "Ana Pérez",
  username: "ana",
  role: "viewer",
  joined_at: "2026-10-06T10:00:00+00:00",
  via: "class_link",
  invited_by: "Luis",
  disabled_at: null,
  ...overrides,
});

describe("studentsOf", () => {
  it("keeps the students alone, paused ones included, by name", () => {
    const people = [
      member({ user_id: 1, name: "Zoe", username: "zoe" }),
      member({ user_id: 2, name: "Luis", username: "luis", role: "editor" }),
      member({ user_id: 3, name: "Ana", username: "ana", disabled_at: "2026-10-06T11:00:00+00:00" }),
      member({ user_id: 4, name: "Marta", username: "marta", role: "owner" }),
    ];
    expect(studentsOf(people).map((row) => row.username)).toEqual(["ana", "zoe"]);
  });
});

describe("inFilter", () => {
  const open = member({});
  const paused = member({ disabled_at: "2026-10-06T11:00:00+00:00" });

  it("reads the two filters", () => {
    expect([inFilter(open, "active"), inFilter(paused, "active")]).toEqual([true, false]);
    expect([inFilter(open, "disabled"), inFilter(paused, "disabled")]).toEqual([false, true]);
  });
});

describe("matchesMember", () => {
  it("finds by name or username, whatever the accents and the case", () => {
    expect(matchesMember(member({}), "perez")).toBe(true);
    expect(matchesMember(member({}), "ANA")).toBe(true);
    expect(matchesMember(member({}), "luis")).toBe(false);
    expect(matchesMember(member({}), "  ")).toBe(true);
  });
});

describe("viaKey", () => {
  it("names the known origins and nothing else", () => {
    expect(viaKey("class_link")).toBe("class.via.classLink");
    expect(viaKey("invite")).toBe("class.via.invite");
    expect(viaKey("admin")).toBe("class.via.admin");
    expect(viaKey(null)).toBeNull();
    expect(viaKey("somewhere")).toBeNull();
  });
});
