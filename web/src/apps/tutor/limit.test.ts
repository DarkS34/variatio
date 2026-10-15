import { describe, expect, it } from "vitest";

import { translator } from "@/lib/i18n";

import "./i18n";
import { limitSentence } from "./limit";

/* The daily limit's refusal is built from its code and `Retry-After`, in the reader's
   language, with the server's own sentence as the fallback when the header is absent. */

const ES = translator("es");

describe("limitSentence", () => {
  it("says when the next message can go", () => {
    expect(limitSentence(90 * 60, "servidor", ES)).toBe(
      "Has llegado al límite diario de mensajes al tutor. Podrás escribir otra vez dentro de 1 hora y 30 minutos.",
    );
  });

  it("falls back to the server's sentence without a wait", () => {
    expect(limitSentence(null, "La frase del servidor.", ES)).toBe("La frase del servidor.");
  });
});
