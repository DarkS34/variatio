import { describe, expect, it } from "vitest";

import { USES } from "@/lib/steps";

import { CONFIG_STAGES, stageOfDoor } from "./stages";

describe("the configuration's stages and «Funciones»", () => {
  it("draws each door's own stage in «Funciones»", () => {
    // Swapped door keys pass every other gate: each row would draw another's settings.
    expect(stageOfDoor("generate").key).toBe("generation");
    expect(stageOfDoor("compare").key).toBe("evaluation");
    expect(stageOfDoor("tutor").key).toBe("tutoring");
    expect(stageOfDoor("chat").key).toBe("chat");
  });

  it("names each door's stage as the bar names the door, with its function", () => {
    for (const door of USES) {
      expect(stageOfDoor(door.key).labelKey).toBe(door.labelKey);
      expect(stageOfDoor(door.key).feature).toBe(door.feature);
      expect(stageOfDoor(door.key).access).toBe(door.access);
    }
  });

  it("leaves «Configuración» the construction's stages, in the path's order", () => {
    const construction = CONFIG_STAGES.filter((stage) => stage.door === null);
    // The types of exercise have no screen of their own: they are the bank's step's first part.
    expect(construction.map((stage) => stage.key)).toEqual(["transcription", "graph", "bank"]);
    expect(construction.map((stage) => stage.number)).toEqual(["1", "2", "3"]);
  });
});
