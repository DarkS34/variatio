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
