import type { Key } from "@/lib/i18n";
import type { ArtifactStatus } from "@/lib/types";

export type StatusKey = ArtifactStatus | "blocked";
export type Shape = "disc" | "ring" | "broken" | "sweep" | "dash" | "lock";
export type Tone = "settled" | "attention" | "primary" | "muted";

export interface StatusMeta {
  labelKey: Key;
  shape: Shape;
  tone: Tone;
}

// No state is encoded by colour alone, and this is the only copy of that rule. There used
// to be three different drawings of the same concept — the dot in the navbar, the stage
// badge and the dashboard card — each with its own colour map and none with a shape: for
// anyone who cannot tell red from green, "stale" and "approved" were the same 6 px circle.
export const STATUS: Record<StatusKey, StatusMeta> = {
  approved: { labelKey: "status.approved", shape: "disc", tone: "settled" },
  draft: { labelKey: "status.draft", shape: "ring", tone: "attention" },
  stale: { labelKey: "status.stale", shape: "broken", tone: "attention" },
  building: { labelKey: "status.building", shape: "sweep", tone: "primary" },
  missing: { labelKey: "status.missing", shape: "dash", tone: "muted" },
  blocked: { labelKey: "status.blocked", shape: "lock", tone: "muted" },
};

// Blocked wins over the status: a blocked stage is not "not built yet", it is "not your
// turn yet", and that is the one to read first.
export function statusKey(status: ArtifactStatus, blocked: boolean): StatusKey {
  return blocked ? "blocked" : status;
}

// The graph canvas cannot use Tailwind classes; it reads the variables with
// getComputedStyle. Keeping the names here is what stops the curriculum view painting
// "covered" in a different green from the one the navbar uses.
export const TONE_VAR: Record<Tone, string> = {
  settled: "--settled",
  attention: "--attention",
  primary: "--primary",
  muted: "--muted-foreground",
};
