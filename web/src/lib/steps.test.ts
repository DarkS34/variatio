import { describe, expect, it } from "vitest";

import { STEPS, currentStepPath, nextStepOf, stepBusy, stepStates } from "./steps";
import type { ArtifactStatus, Job, StageState } from "./types";

const stage = (artifact: string, status: ArtifactStatus): StageState =>
  ({ artifact, status, stale_because: [] }) as unknown as StageState;

const chain = (...statuses: ArtifactStatus[]) =>
  [
    stage("exemplars_profile", statuses[0]),
    stage("knowledge_graph", statuses[1]),
    stage("exemplars_bank", statuses[2]),
  ] as StageState[];

describe("stepStates", () => {
  it("marks exactly one step as the next move", () => {
    // Lo que hace obvio un camino es UN movimiento siguiente, no una lista de pendientes.
    const states = stepStates(chain("missing", "missing", "missing"), true);
    expect(states.filter((s) => s === "now")).toHaveLength(1);
    expect(states).toEqual(["done", "now", "later", "later"]);
  });

  it("puts the first step in play while an origin has no documents", () => {
    expect(stepStates(chain("approved", "approved", "approved"), false)[0]).toBe("now");
  });

  it("only an approved stage counts as done", () => {
    // Construido no es aprobado: mientras nadie lo dé por bueno, el paso sigue abierto.
    const states = stepStates(chain("draft", "missing", "missing"), true);
    expect(states[1]).toBe("now");
  });

  it("a stale stage stops being done, and the path goes back to it", () => {
    // Y el que va DETRÁS sigue marcado como hecho, que es la verdad: está aprobado. El
    // camino te devuelve al que se ha quedado desfasado sin borrar lo que sí cerraste.
    const states = stepStates(chain("approved", "stale", "approved"), true);
    expect(states).toEqual(["done", "done", "now", "done"]);
  });

  it("leaves nothing in play once the whole path is walked", () => {
    const states = stepStates(chain("approved", "approved", "approved"), true);
    expect(states.every((s) => s === "done")).toBe(true);
  });
});

describe("currentStepPath", () => {
  it("answers with the step that is next", () => {
    expect(currentStepPath(chain("approved", "missing", "missing"), true)).toBe("/prepare/graph");
  });

  it("answers with the first step when there is nothing uploaded", () => {
    expect(currentStepPath(chain("missing", "missing", "missing"), false)).toBe("/raw");
  });

  it("answers with generation once everything is approved", () => {
    // Es para lo que servía todo lo anterior; dejarlo en el último paso sería devolver a
    // alguien a una pantalla que ya ha terminado.
    expect(currentStepPath(chain("approved", "approved", "approved"), true)).toBe("/generate");
  });

  it("only ever answers a path the bar itself draws", () => {
    const paths = STEPS.map((s) => s.path) as string[];
    expect(paths).toContain(currentStepPath(chain("approved", "missing", "missing"), true));
  });
});

describe("the order of the path", () => {
  it("is the raw material, then review.ARTIFACTS", () => {
    // El perfil va antes que el temario porque cerrar el temario necesita el perfil
    // APROBADO: empezar por el temario es empezar por un paso que no se puede terminar.
    expect(STEPS.map((s) => s.artifact)).toEqual([
      null,
      "exemplars_profile",
      "knowledge_graph",
      "exemplars_bank",
    ]);
  });
});

describe("nextStepOf", () => {
  it("leads the raw material to the first stage, numbered", () => {
    // El paso sin artefacto ofrece el mismo «Continuar» que los demás, leído de la misma lista.
    expect(nextStepOf(null)).toEqual({
      path: "/prepare/profile",
      number: "1.2",
      labelKey: "nav.step.profile",
    });
  });

  it("leads the last stage to generation, unnumbered", () => {
    expect(nextStepOf("exemplars_bank")).toEqual({
      path: "/generate",
      number: null,
      labelKey: "nav.create",
    });
  });
});

describe("stepBusy", () => {
  const job = (over: Partial<Job>): Job =>
    ({ kind: "build_kg", artifact: "knowledge_graph", status: "running", ...over }) as Job;

  it("spins a stage that is building and not queued", () => {
    const busy = stepBusy(chain("approved", "building", "missing"), [job({})]);
    expect(busy).toEqual([false, false, true, false]);
  });

  it("does not spin over a build still waiting in the queue", () => {
    // Un trabajo en cola no está en marcha, y la rueda afirma que algo está pasando.
    const busy = stepBusy(chain("approved", "building", "missing"), [
      job({ status: "queued", queue_position: 2 }),
    ]);
    expect(busy[2]).toBe(false);
  });

  it("believes the pipeline when the stream knows no job for the artifact", () => {
    expect(stepBusy(chain("approved", "building", "missing"), [])[2]).toBe(true);
  });

  it("spins step 1 while the documents are being read, and only then", () => {
    const reading = job({ kind: "transcribe", artifact: null, status: "running" });
    expect(stepBusy(chain("missing", "missing", "missing"), [reading])[0]).toBe(true);
    const queued = job({ kind: "transcribe", artifact: null, status: "queued", queue_position: 1 });
    expect(stepBusy(chain("missing", "missing", "missing"), [queued])[0]).toBe(false);
  });
});
