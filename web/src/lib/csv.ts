/**
 * A CSV the teacher downloads, written so a spreadsheet opens it as data.
 *
 * The cells are names somebody typed, so one opening with `=`, `+`, `-`, `@` or a control
 * character is defused with a leading apostrophe — the rule `server/csv_safe.py` keeps for
 * the server's exports, numbers exempt. Quoting is not the defusing (the parser strips the
 * quotes before typing the cell); it is what keeps a comma or a line break inside one cell.
 */

const FORMULA_LEAD = ["=", "+", "-", "@", "\t", "\r", "\n"];
const NUMBER = /^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$/;

/** Prefix an apostrophe to a value a spreadsheet would read as a formula. */
export function defuse(value: string): string {
  if (!FORMULA_LEAD.some((lead) => value.startsWith(lead))) return value;
  return NUMBER.test(value) ? value : `'${value}`;
}

/** One cell: defused, then quoted when it holds a comma, a quote or a line break. */
export function csvCell(value: string): string {
  const safe = defuse(value);
  return /[",\r\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

/** A whole file: a header row and one row per record, lines ended CRLF as RFC 4180 asks. */
export function csvFile(header: string[], rows: string[][]): string {
  return [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

/**
 * Hand a CSV to the browser to save. The byte-order mark is what makes a spreadsheet read
 * the accents of a name as UTF-8 instead of guessing the system's code page.
 */
export function saveCsv(name: string, content: string): void {
  const url = URL.createObjectURL(new Blob(["\uFEFF", content], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}
