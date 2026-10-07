import { describe, expect, it } from "vitest";

import { addDays, areaOf, findingsIn, intensity, kindShares, sayFindings, weekBefore, weekLabel } from "./activity";
import { translator } from "./i18n";

const es = translator("es");

describe("weekLabel", () => {
  const current = { week: "2026-W41", start: "2026-10-05" };

  it("names this week and the one before, and any other by its days", () => {
    expect(weekLabel(current, current, es.t)).toBe("Esta semana");
    expect(weekLabel({ week: "2026-W40", start: "2026-09-28" }, current, es.t)).toBe("Semana pasada");
    expect(weekLabel({ week: "2026-W39", start: "2026-09-21" }, current, es.t)).toMatch(/21.*27/);
  });

  it("adds days across a month", () => {
    expect(addDays("2026-09-28", 6)).toBe("2026-10-04");
  });
});

describe("kindShares", () => {
  it("keeps the four kinds that work on the subject in order and folds the rest", () => {
    expect(
      kindShares({ solution: 2, theory: 5, social: 1, blocked: 1, attempt: 0 }).map((s) => [s.key, s.value]),
    ).toEqual([
      ["theory", 5],
      ["solution", 2],
      ["other", 2],
    ]);
  });
});

describe("sayFindings", () => {
  it("words each finding and gives the attention to the first a teacher can act on", () => {
    const views = sayFindings(
      [
        { kind: "trend", active: 7, previous: 12, open: true, area: "tutor" },
        {
          kind: "asked",
          concept: "Recursividad",
          students: 12,
          of: 30,
          prerequisite: "Funciones",
          sent_back: 7,
        },
        { kind: "idle", students: 8, of: 30, open: true, area: "exercises" },
      ],
      es,
    );
    expect(views.map((view) => view.act)).toEqual([false, true, false]);
    expect(views[1]).toEqual({
      figure: "12",
      text: "12 de 30 alumnos preguntaron por «Recursividad». A 7 el tutor les mandó repasar «Funciones».",
      act: true,
    });
    expect(views[0].text).toBe("7 alumnos usaron el tutor, 5 menos que la semana anterior.");
    expect(views[2].text).toBe("8 de 30 alumnos todavía no han generado ningún ejercicio esta semana.");
  });

  it("says a quiet student by the page it is read on", () => {
    const [tutor, exercises] = sayFindings(
      [
        { kind: "quiet", open: false, area: "tutor" },
        { kind: "quiet", open: false, area: "exercises" },
      ],
      es,
    );
    expect(tutor.text).toBe("No escribió al tutor esa semana.");
    expect(exercises.text).toBe("No generó ningún ejercicio esa semana.");
  });
});

describe("findingsIn", () => {
  it("keeps a page's findings, reading the kind where an older API sent no area", () => {
    const findings = [
      { kind: "topic", concept: "Bucle", messages: 3 } as const,
      { kind: "practised", unit: "Tema 1", exercises: 2 } as const,
      { kind: "idle", students: 1, of: 3, open: true, area: "tutor" } as const,
    ];
    expect(findingsIn(findings, "tutor").map((f) => f.kind)).toEqual(["topic", "idle"]);
    expect(findingsIn(findings, "exercises").map((f) => f.kind)).toEqual(["practised"]);
    expect(areaOf({ kind: "idle", students: 1, of: 3, open: true })).toBe("exercises");
  });
});

describe("weekBefore", () => {
  const weeks = [
    { week: "2026-W41", start: "2026-10-05", messages: 2, exercises: 1, active: 1, digest: false },
    { week: "2026-W40", start: "2026-09-28", messages: 0, exercises: 4, active: 2, digest: false },
  ];

  it("finds the week before, and none before the first", () => {
    expect(weekBefore(weeks, "2026-W41")?.exercises).toBe(4);
    expect(weekBefore(weeks, "2026-W40")).toBeNull();
    expect(weekBefore(weeks, "2026-W30")).toBeNull();
  });
});

describe("intensity", () => {
  it("paints nothing for zero and something visible for one", () => {
    expect(intensity(0, 5)).toBe(0);
    expect(intensity(1, 5)).toBeGreaterThan(0.18);
    expect(intensity(5, 5)).toBe(1);
  });
});
