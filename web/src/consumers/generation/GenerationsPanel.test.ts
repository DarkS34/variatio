import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

// The session's modules read the tab's storage when they load; node has none, so each gets
// an empty one in memory before anything is imported.
vi.hoisted(() => {
  const memory = (): Storage => {
    const held = new Map<string, string>();
    return {
      get length() {
        return held.size;
      },
      clear: () => held.clear(),
      getItem: (key) => held.get(key) ?? null,
      key: (index) => [...held.keys()][index] ?? null,
      removeItem: (key) => void held.delete(key),
      setItem: (key, value) => void held.set(key, String(value)),
    };
  };
  globalThis.sessionStorage ??= memory();
  globalThis.localStorage ??= memory();
});

import { localeStore } from "@/lib/i18n";
import type { ExemplarsProfile, GenerationRow } from "@/lib/types";

import { GenerationCard } from "./GenerationsPanel";

const PROFILE: ExemplarsProfile = {
  item_types: {
    ejercicio: {
      primary_field: "enunciado",
      fields: {
        enunciado: { schema: { type: "string" } },
        nivel_dificultad: { schema: { type: "string" } },
      },
    },
  },
};

/** An older API's row: no `promotable`, nothing promoted, so the card draws no bank button
 *  and needs no query client. */
function row(fixed: Record<string, unknown>, item: Record<string, unknown>): GenerationRow {
  return {
    id: "20261019T100000Z-abcd",
    created_at: 0,
    job_id: null,
    item_type: "ejercicio",
    concepts: ["Recursividad"],
    curriculum: [],
    fixed,
    instructions: "",
    think: true,
    model: null,
    author: { id: 1, name: null, username: "profe.ana" },
    promoted_item_id: null,
    item,
  };
}

function card(generation: GenerationRow, expanded = true): string {
  return renderToStaticMarkup(
    createElement(GenerationCard, {
      row: generation,
      profile: PROFILE,
      expanded,
      onToggle: () => undefined,
    }),
  );
}

beforeAll(() => localeStore.adopt("es"));

describe("GenerationCard", () => {
  it("draws a pinned field the exercise shows once, under its label", () => {
    const html = card(
      row({ nivel_dificultad: "avanzado" }, { enunciado: "Suma recursiva.", nivel_dificultad: "avanzado" }),
    );
    expect(html.match(/avanzado/g)).toHaveLength(1);
    expect(html).not.toContain("nivel_dificultad");
  });

  it("keeps in the commission a pinned field the exercise does not show", () => {
    const html = card(row({ nivel_dificultad: "avanzado" }, { enunciado: "Suma recursiva." }));
    expect(html.match(/avanzado/g)).toHaveLength(1);
    expect(html).toContain("nivel dificultad");
    expect(html).not.toContain("nivel_dificultad");
  });

  it("heads the card with its gestures, before what the exercise is", () => {
    const html = card(row({}, { enunciado: "Suma recursiva." }), false);
    expect(html.indexOf("Copiar JSON")).toBeGreaterThan(-1);
    expect(html.indexOf("Copiar JSON")).toBeLessThan(html.indexOf("Recursividad"));
  });
});
