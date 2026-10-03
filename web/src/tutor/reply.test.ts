import { describe, expect, it } from "vitest";

import { splitReply } from "./reply";

describe("splitReply", () => {
  it("takes the closing paragraph that asks, and leaves an earlier question in the body", () => {
    const text = [
      "Pregúntate: ¿puedo dividirlo en una versión más pequeña?",
      "En los apuntes se dice que una función se define en términos de sí misma.",
      "¿Qué pasaría si nunca llegara al caso más simple?",
    ].join("\n\n");
    expect(splitReply(text)).toEqual({
      body: [
        "Pregúntate: ¿puedo dividirlo en una versión más pequeña?",
        "En los apuntes se dice que una función se define en términos de sí misma.",
      ].join("\n\n"),
      questions: "¿Qué pasaría si nunca llegara al caso más simple?",
    });
  });

  it("keeps the lead-in of the asking paragraph with the explanation", () => {
    const text =
      "Una función se puede llamar varias veces.\n\n" +
      "Piensa en el ejemplo del factorial. Si la función `factorial` se llama a sí misma, ¿qué parte la detiene?";
    expect(splitReply(text)).toEqual({
      body: "Una función se puede llamar varias veces.\n\nPiensa en el ejemplo del factorial.",
      questions: "Si la función `factorial` se llama a sí misma, ¿qué parte la detiene?",
    });
  });

  it("takes every question the reply closes with", () => {
    const text = "Vas bien.\n\n¿Qué devuelve con 0? ¿Y con 1?\n\n¿Qué tienen en común?";
    expect(splitReply(text)).toEqual({
      body: "Vas bien.",
      questions: "¿Qué devuelve con 0? ¿Y con 1?\n\n¿Qué tienen en común?",
    });
  });

  it("never cuts inside code, a formula, an emphasis or an abbreviation", () => {
    expect(splitReply("Mira `a. B` y $x. Y$ antes, p. ej. aquí, ¿qué ves?").body).toBe("");
    expect(splitReply("Fíjate en **esto. ¿Qué es?**")).toEqual({
      body: "",
      questions: "Fíjate en **esto. ¿Qué es?**",
    });
  });

  it("leaves a reply that does not close asking as it is", () => {
    const text = "¿Qué recuerdas de «Recursividad»? Léelo y cuéntame qué hace.";
    expect(splitReply(text)).toEqual({ body: text, questions: "" });
  });

  it("takes a closing list of questions whole and a fence as one block", () => {
    const text = "Mira tu código:\n\n```python\nx = 1\n\ny = 2\n```\n\n- ¿Qué vale x?\n- ¿Y qué vale y?";
    expect(splitReply(text)).toEqual({
      body: "Mira tu código:\n\n```python\nx = 1\n\ny = 2\n```",
      questions: "- ¿Qué vale x?\n- ¿Y qué vale y?",
    });
  });
});
