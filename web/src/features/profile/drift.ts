export type DriftAspect = "type" | "enum" | "decided_by";

export interface ProfileDrift {
  added: { field: string; item_types: string[] }[];
  removed: { field: string; item_types: string[]; decided_by: "user" | "model" }[];
  changed: { field: string; item_types: string[]; aspects: DriftAspect[] }[];
}

export interface ProfilePendingDraft {
  drift: ProfileDrift;
  path: string;
  newer: boolean;
}

export function hasDrift(drift: ProfileDrift): boolean {
  return drift.added.length + drift.removed.length + drift.changed.length > 0;
}

export function modalities(count: number): string {
  return count === 1 ? "1 modalidad" : `${count} modalidades`;
}

const ASPECT_LABELS: Record<DriftAspect, string> = {
  type: "el tipo",
  enum: "los valores posibles",
  decided_by: "quién lo decide",
};

export function aspectList(aspects: DriftAspect[]): string {
  return aspects.map((aspect) => ASPECT_LABELS[aspect]).join(", ");
}
