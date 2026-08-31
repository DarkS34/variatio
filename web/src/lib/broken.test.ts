import { describe, expect, it } from "vitest";
import { hasBrokenText } from "./fields";

describe("hasBrokenText", () => {
  it("marca el daño real del corpus", () => {
    expect(hasBrokenText("\x1fQu\x10\x10")).toBe(true);
    expect(hasBrokenText("Escribe un código que imprima tu nombre")).toBe(false);
  });
  it("no confunde saltos de línea ni tabuladores con daño", () => {
    expect(hasBrokenText("linea 1\nlinea 2\tcol")).toBe(false);
    expect(hasBrokenText("\r\n")).toBe(false);
  });
  it("baja por listas y objetos", () => {
    expect(hasBrokenText({ a: ["ok", "ma\x10l"] })).toBe(true);
    expect(hasBrokenText({ a: ["ok", "bien"] })).toBe(false);
  });
  it("ignora lo que no es texto", () => {
    expect(hasBrokenText(42)).toBe(false);
    expect(hasBrokenText(null)).toBe(false);
  });
});
