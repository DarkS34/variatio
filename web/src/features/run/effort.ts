import type { Key } from "@/lib/i18n";

import { familyOf, type ModelFamily } from "./models";

export type EffortLevel = "low" | "medium" | "high" | "max";

export const EFFORT_ORDER: EffortLevel[] = ["low", "medium", "high", "max"];

export const EFFORT_LABELS: Record<EffortLevel, Key> = {
  low: "effort.low",
  medium: "effort.medium",
  high: "effort.high",
  max: "effort.max",
};

/* How much a model may deliberate is a property OF THE MODEL, so which levels exist and
   what to warn about are declared once, beside everything else the screen knows about it
   (`models.ts`). What lives here is the scale itself and the three questions asked of it. */

export function effortPolicy(model: string | undefined): ModelFamily {
  return familyOf(model);
}

export function clampEffort(level: EffortLevel, policy: ModelFamily): EffortLevel {
  return policy.levels.includes(level) ? level : policy.levels[policy.levels.length - 1];
}

export function effortWarning(level: EffortLevel, policy: ModelFamily): Key | null {
  if (!policy.warnAbove || !policy.warningKey) return null;
  return EFFORT_ORDER.indexOf(level) > EFFORT_ORDER.indexOf(policy.warnAbove)
    ? policy.warningKey
    : null;
}
