import { describe, expect, it } from "vitest";

import { ensureCatalogue, translator } from "@/lib/i18n";

import "./i18n";
import { limitSentence, waitInWords } from "./limit";

/* The daily limit's refusal is built from its code and `Retry-After`, in the reader's
   language, with the server's own sentence as the fallback when the header is absent. */

const ES = translator("es");

describe("waitInWords", () => {
  it("says hours and minutes, with the server's rounding", () => {
    expect(waitInWords(3 * 3600 + 12 * 60 + 40, ES)).toBe("3 horas y 12 minutos");
    expect(waitInWords(3600 + 60, ES)).toBe("1 hora y 1 minuto");
  });

  it("leaves out the part that is zero", () => {
    expect(waitInWords(2 * 3600, ES)).toBe("2 horas");
    expect(waitInWords(25 * 60, ES)).toBe("25 minutos");
  });

  it("never says less than a minute", () => {
    expect(waitInWords(5, ES)).toBe("1 minuto");
    expect(waitInWords(0, ES)).toBe("1 minuto");
  });

  it("speaks the reader's language", async () => {
    await ensureCatalogue("en");
    expect(waitInWords(2 * 3600 + 5 * 60, translator("en"))).toBe("2 hours and 5 minutes");
  });
});

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
