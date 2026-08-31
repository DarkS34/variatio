import { describe, expect, it } from "vitest";
import { readableValue } from "./text";

describe("readableValue", () => {
  it("capitaliza los valores del perfil de referencia", () => {
    expect(readableValue("basico")).toBe("Basico");
    expect(readableValue("intermedio")).toBe("Intermedio");
  });
  it("convierte separadores en espacios", () => {
    expect(readableValue("opcion_multiple")).toBe("Opcion multiple");
    expect(readableValue("respuesta-corta")).toBe("Respuesta corta");
  });
  it("no toca lo que ya está bien escrito", () => {
    expect(readableValue("Avanzado")).toBe("Avanzado");
  });
  it("devuelve el valor tal cual si no queda nada que capitalizar", () => {
    expect(readableValue("_")).toBe("_");
    expect(readableValue("")).toBe("");
  });
});
