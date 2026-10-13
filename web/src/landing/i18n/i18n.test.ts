import { describe, expect, it } from "vitest";

import { ensureCatalogue, translate } from "@/lib/i18n";
import { es as core } from "@/lib/i18n/es";
import { describeCatalogue } from "@/lib/i18n/testing";

import { en } from "./en";
import { es } from "./es";
import "./index";

describeCatalogue("the landing's catalogues", es, en);

describe("the landing's keys", () => {
  it("are none of the core's", () => {
    expect(Object.keys(es).filter((key) => key in core)).toEqual([]);
  });

  it("all start with the landing's namespace", () => {
    expect(Object.keys(es).filter((key) => !key.startsWith("landing."))).toEqual([]);
  });
});

describe("registering the landing's catalogue", () => {
  it("makes its keys readable in Spanish at once and in English once fetched", async () => {
    expect(translate("es", "landing.join.title")).toBe(es["landing.join.title"]);
    await ensureCatalogue("en");
    expect(translate("en", "landing.join.title")).toBe(en["landing.join.title"]);
  });
});
