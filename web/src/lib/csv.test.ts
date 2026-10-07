import { describe, expect, it } from "vitest";

import { csvCell, csvFile, defuse } from "./csv";

describe("csv", () => {
  it("defuses what a spreadsheet would run, and leaves numbers alone", () => {
    expect(defuse("=SUMA(A1)")).toBe("'=SUMA(A1)");
    expect(defuse("+34 600")).toBe("'+34 600");
    expect(defuse("-12")).toBe("-12");
    expect(defuse("@ana")).toBe("'@ana");
    expect(defuse("Ana Pérez")).toBe("Ana Pérez");
  });

  it("quotes a cell holding a comma or a quote, after defusing it", () => {
    expect(csvCell("Pérez, Ana")).toBe('"Pérez, Ana"');
    expect(csvCell('Ana "la jefa"')).toBe('"Ana ""la jefa"""');
    expect(csvCell("=1,2")).toBe('"\'=1,2"');
  });

  it("writes a header and one CRLF row per record", () => {
    expect(csvFile(["nombre", "enlace"], [["Ana", "https://x/invite?token=a"]])).toBe(
      "nombre,enlace\r\nAna,https://x/invite?token=a\r\n",
    );
  });
});
