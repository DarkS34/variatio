export function isEmptyField(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return true;
  return Array.isArray(value) && value.length === 0;
}

export function fieldText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) {
    return value
      .map((entry) => fieldText(entry))
      .filter((entry) => entry.trim() !== "")
      .map((entry) => `- ${entry}`)
      .join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, entry]) => entry !== null && entry !== undefined)
      .map(([key, entry]) => `- ${key}: ${fieldText(entry)}`)
      .join("\n");
  }
  return String(value);
}

export function fieldToInput(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map((entry) => String(entry)).join("\n");
  return String(value);
}

export function inputToField(raw: string, wasList: boolean): unknown {
  if (!wasList) return raw === "" ? null : raw;
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "");
}

/**
 * Whether a value carries C0 control characters, which in this corpus means damage.
 *
 * A bank extracted under Cerebras' constrained decoding holds text where every non-ASCII
 * character came back as `\u00` plus two wrong hex digits, so "¿Qué" reached the file as
 * `\x1fQu\x10\x10`. It is not recoverable in place — only a re-extraction restores it — and
 * without this the screen paints those items exactly like sound ones.
 *
 * Tab, newline and carriage return are legitimate in a statement and are not damage.
 */
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/;

export function hasBrokenText(value: unknown): boolean {
  if (typeof value === "string") return CONTROL.test(value);
  if (Array.isArray(value)) return value.some(hasBrokenText);
  if (value && typeof value === "object") return Object.values(value).some(hasBrokenText);
  return false;
}
