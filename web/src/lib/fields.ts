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
