import { describe, expect, it } from "vitest";

import { ensureCatalogue, translate } from "@/lib/i18n";
import { es as core } from "@/lib/i18n/es";
import { describeCatalogue } from "@/lib/i18n/testing";

import { en } from "./en";
import { es } from "./es";
import "./index";

describeCatalogue("the evaluation's catalogues", es, en);

describe("the evaluation's keys", () => {
  it("are none of the core's", () => {
    // Registering merges them into the same table: a shared key would be overwritten by
    // whichever catalogue arrived last.
    expect(Object.keys(es).filter((key) => key in core)).toEqual([]);
  });
});

describe("registering the evaluation's catalogue", () => {
  it("makes its keys readable in Spanish at once and in English once fetched", async () => {
    expect(translate("es", "eval.title")).toBe(es["eval.title"]);
    await ensureCatalogue("en");
    expect(translate("en", "eval.title")).toBe(en["eval.title"]);
  });
});
