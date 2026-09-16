import { describe, expect, it } from "vitest";

import {
  changesOf,
  draftOf,
  fromLocalInput,
  inDays,
  inviteState,
  isAhead,
  linkLines,
  matchesInvite,
  newDraft,
  termsOf,
  toLocalInput,
} from "./invites";

describe("toLocalInput / fromLocalInput", () => {
  it("round-trips a moment to the minute, in the reader's own zone", () => {
    const moment = new Date(2031, 0, 5, 9, 7, 42, 500);
    const value = toLocalInput(moment);
    expect(value).toBe("2031-01-05T09:07");
    expect(fromLocalInput(value)?.getTime()).toBe(new Date(2031, 0, 5, 9, 7).getTime());
  });

  it("names no moment for what the control can hold while it is half filled", () => {
    expect(fromLocalInput("")).toBeNull();
    expect(fromLocalInput("2031-01-05")).toBeNull();
    expect(fromLocalInput("2031-13-45T99:99")).toBeNull();
  });
});

describe("inDays", () => {
  it("counts calendar days and drops the seconds", () => {
    const now = new Date(2026, 8, 16, 17, 50, 33, 120);
    const week = inDays(7, now);
    expect([week.getMonth(), week.getDate(), week.getHours(), week.getMinutes()]).toEqual([
      8, 23, 17, 50,
    ]);
    expect(week.getSeconds()).toBe(0);
    expect(week.getMilliseconds()).toBe(0);
  });

  it("rolls over the end of a month", () => {
    const month = inDays(30, new Date(2026, 8, 16, 8, 0));
    expect([month.getMonth(), month.getDate()]).toEqual([9, 16]);
  });
});

describe("isAhead", () => {
  const now = new Date(2026, 8, 16, 12, 0).getTime();

  it("takes only a moment still to come", () => {
    expect(isAhead("2026-09-16T12:01", now)).toBe(true);
    expect(isAhead("2026-09-16T12:00", now)).toBe(false);
    expect(isAhead("2020-01-01T00:00", now)).toBe(false);
    expect(isAhead("", now)).toBe(false);
  });

  it("has no upper bound", () => {
    expect(isAhead("2999-12-31T23:59", now)).toBe(true);
  });
});

describe("inviteState", () => {
  const now = Date.UTC(2026, 8, 16, 12);

  it("believes the server", () => {
    expect(inviteState({ state: "expired", expires_at: "2099-01-01T00:00:00Z" }, now)).toBe(
      "expired",
    );
  });

  it("reads the date when an older API sends no state", () => {
    expect(inviteState({ expires_at: "2026-09-16T12:00:01Z" }, now)).toBe("pending");
    expect(inviteState({ expires_at: "2026-09-16T12:00:00Z" }, now)).toBe("expired");
  });
});

describe("matchesInvite", () => {
  const row = {
    label: "Profesora de Enfermería",
    workspace: "Farmacología",
    workspace_slug: "enfermeria-farmacologia",
    created_by: "admin",
  };

  it("matches the alias, the asignatura and the author, without accents or case", () => {
    expect(matchesInvite(row, "  enfermeria ")).toBe(true);
    expect(matchesInvite(row, "FARMACO")).toBe(true);
    expect(matchesInvite(row, "admin")).toBe(true);
    expect(matchesInvite(row, "alumno")).toBe(false);
  });

  it("lets everything through an empty search, and survives a row with nothing named", () => {
    expect(matchesInvite(row, "")).toBe(true);
    const bare = { label: null, workspace: null, workspace_slug: null, created_by: null };
    expect(matchesInvite(bare, "x")).toBe(false);
  });
});

describe("linkLines", () => {
  const minted = (label: string | null, link: string) => ({
    invite: {
      id: 1,
      label,
      role: "editor" as const,
      workspace: null,
      workspace_slug: null,
      created_at: "",
      expires_at: "",
      created_by: null,
    },
    link,
  });

  it("puts the alias and the link in two columns", () => {
    expect(linkLines([minted("Alumno 1", "https://a"), minted("Alumno 2", "https://b")])).toBe(
      "Alumno 1\thttps://a\nAlumno 2\thttps://b",
    );
  });

  it("is only links when nothing is named, and keeps the columns when one is", () => {
    expect(linkLines([minted(null, "https://a"), minted(null, "https://b")])).toBe(
      "https://a\nhttps://b",
    );
    expect(linkLines([minted("Ana", "https://a"), minted(null, "https://b")])).toBe(
      "Ana\thttps://a\n\thttps://b",
    );
  });
});

describe("the form's terms", () => {
  const row = {
    label: "Ana",
    workspace_slug: "enfermeria",
    role: "owner" as const,
    expires_at: new Date(2020, 0, 1, 9, 30, 45).toISOString(),
  };

  it("starts a new invitation on the default week, with no alias", () => {
    const draft = newDraft("enfermeria", new Date(2026, 8, 16, 18, 5, 12));
    expect(draft).toEqual({
      label: "",
      workspace: "enfermeria",
      role: "editor",
      expires: "2026-09-23T18:05",
    });
    expect(newDraft(undefined).workspace).toBe("");
  });

  it("sends what the form holds, trimmed, with «ninguna» as null", () => {
    const terms = termsOf({ label: "  ", workspace: "", role: "viewer", expires: "2031-01-05T09:07" });
    expect(terms).toEqual({
      workspace: null,
      role: "viewer",
      expires_at: new Date(2031, 0, 5, 9, 7).toISOString(),
      label: null,
    });
    expect(termsOf({ label: "", workspace: "", role: "viewer", expires: "" })).toBeNull();
  });

  it("changes nothing when nothing was touched, even with seconds on the stored date", () => {
    expect(changesOf(row, draftOf(row))).toEqual({});
  });

  it("renames an expired invitation without moving its date", () => {
    expect(changesOf(row, { ...draftOf(row), label: " Ana López " })).toEqual({
      label: "Ana López",
    });
  });

  it("sends each changed term, and «ninguna» and an emptied alias as null", () => {
    const draft = { label: "", workspace: "", role: "viewer" as const, expires: "2031-01-05T09:07" };
    expect(changesOf(row, draft)).toEqual({
      label: null,
      workspace: null,
      role: "viewer",
      expires_at: new Date(2031, 0, 5, 9, 7).toISOString(),
    });
  });

  it("leaves a half-typed date out rather than sending it", () => {
    expect(changesOf(row, { ...draftOf(row), expires: "2031-01" })).toEqual({});
  });
});
