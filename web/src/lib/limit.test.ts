import { describe, expect, it } from "vitest";

import { ensureCatalogue, translator } from "@/lib/i18n";

import { GENERATION_DAILY_LIMIT, launchError, leftToday, waitInWords } from "./limit";

/* A limit's refusal is built from its code and `Retry-After`, in the reader's language, with
   the server's own sentence as the fallback when the header is absent. */

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

describe("launchError", () => {
  it("says when a student may ask again", () => {
    const refused = { message: "servidor", code: GENERATION_DAILY_LIMIT, retryAfter: 90 * 60 };
    expect(launchError(refused, ES)).toBe(
      "Has llegado al límite de ejercicios de hoy. Podrás pedir más dentro de 1 hora y 30 minutos.",
    );
  });

  it("keeps the server's sentence for anything else, or without a wait", () => {
    expect(launchError({ message: "Pide 2 o menos." }, ES)).toBe("Pide 2 o menos.");
    expect(launchError({ message: "Frase.", code: GENERATION_DAILY_LIMIT, retryAfter: null }, ES)).toBe(
      "Frase.",
    );
  });
});

describe("leftToday", () => {
  it("counts what is left, never under zero, and nothing without a limit", () => {
    expect(leftToday({ daily_items: 10, used_today: 4 })).toBe(6);
    expect(leftToday({ daily_items: 10, used_today: 12 })).toBe(0);
    expect(leftToday({ daily_items: null, used_today: 3 })).toBeNull();
  });
});
