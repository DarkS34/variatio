import type { Key } from "@/lib/i18n";

export type EffortLevel = "low" | "medium" | "high" | "max";

export const EFFORT_ORDER: EffortLevel[] = ["low", "medium", "high", "max"];

export const EFFORT_LABELS: Record<EffortLevel, Key> = {
  low: "effort.low",
  medium: "effort.medium",
  high: "effort.high",
  max: "effort.max",
};

export interface EffortPolicy {
  /** Matched against the start of the resolved generation model's name. */
  match: string;
  levels: EffortLevel[];
  /** Choosing a level ABOVE this one shows `warningKey`. */
  warnAbove?: EffortLevel;
  warningKey?: Key;
  /** Always-visible nuance for this model, warning or not. */
  noteKey?: Key;
}

// To support another generation model, add its entry here: which levels it accepts,
// and what (if anything) the screen should warn about. First prefix match wins.
export const EFFORT_POLICIES: EffortPolicy[] = [
  {
    match: "qwen3.8",
    levels: ["low", "medium", "high", "max"],
    warnAbove: "medium",
    warningKey: "effort.warn.qwen38",
  },
  {
    match: "gemma-4",
    levels: ["low", "medium", "high"],
    noteKey: "effort.note.gemma4",
  },
];

const FALLBACK: EffortPolicy = { match: "", levels: ["low", "medium", "high", "max"] };

export function effortPolicy(model: string | undefined): EffortPolicy {
  if (!model) return FALLBACK;
  return EFFORT_POLICIES.find((policy) => model.startsWith(policy.match)) ?? FALLBACK;
}

export function clampEffort(level: EffortLevel, policy: EffortPolicy): EffortLevel {
  return policy.levels.includes(level) ? level : policy.levels[policy.levels.length - 1];
}

export function effortWarning(level: EffortLevel, policy: EffortPolicy): Key | null {
  if (!policy.warnAbove || !policy.warningKey) return null;
  return EFFORT_ORDER.indexOf(level) > EFFORT_ORDER.indexOf(policy.warnAbove)
    ? policy.warningKey
    : null;
}
