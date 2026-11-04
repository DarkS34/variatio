import { describe, expect, it } from "vitest";

import { passwordAccepted, passwordChecks, usernameFromName } from "./signup";

describe("usernameFromName", () => {
  // The same cases as `tests/server/auth/test_username_from_name.py`: the preview must name
  // what the server makes, before any number.
  it.each([
    ["Ana Pérez García", "ana.perez"],
    ["  María José  ", "maria.jose"],
    ["Ana de la Peña", "ana.pena"],
    ["Luis", "luis"],
    ["Ñoño D'Alembert", "nono.alembert"],
    ["Ana M. Pérez", "ana.perez"],
    ["Al", "al1"],
    ["李华", "usuario"],
  ])("makes %s into %s", (name, username) => {
    expect(usernameFromName(name)).toBe(username);
  });

  it("previews nothing for no name", () => {
    expect(usernameFromName("   ")).toBe("");
  });
});

describe("passwordChecks", () => {
  const who = { name: "Ana Pérez", username: "ana.perez" };

  it("asks for twelve characters, counted as the server counts them", () => {
    expect(passwordChecks("corto", who).length).toBe(false);
    expect(passwordChecks("ñandú-ñandú-", who)).toMatchObject({ length: true, count: 12 });
  });

  it("refuses the name and the username inside it", () => {
    expect(passwordChecks("soy-ana.perez-2026", who).personal).toBe(false);
    expect(passwordChecks("mi ana pérez favorita", who).personal).toBe(false);
    expect(passwordChecks("tren-azul-del-norte", who).personal).toBe(true);
  });

  it("refuses the obvious: a common word, a keyboard run, one character repeated", () => {
    expect(passwordChecks("Contraseña", who).obvious).toBe(false);
    expect(passwordChecks("qwertyuiopqw", who).obvious).toBe(false);
    expect(passwordChecks("aaaaaaaaaaaaaa", who).obvious).toBe(false);
    expect(passwordChecks("", who).obvious).toBe(false);
  });

  it("accepts a passphrase", () => {
    expect(passwordAccepted(passwordChecks("tren azul del norte", who))).toBe(true);
  });
});
