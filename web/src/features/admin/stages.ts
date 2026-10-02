import { Play, type LucideIcon } from "lucide-react";

import type { Key } from "@/lib/i18n";
import { STEPS, USES, stepNumber } from "@/lib/steps";
import type { ConfigSetting } from "@/lib/types";

/**
 * THE CONFIGURATION'S SCREENS ARE THE PATH'S STAGES, named and numbered as the bar names
 * and numbers them: the four construction steps carry their number, the door its icon.
 *
 * The keys are the server's (`variatio.settings.types.STAGES`), matched against what
 * `/api/admin/config` sends; the labels come from `lib/steps.ts`, the one home of the path,
 * so a stage cannot be called one thing in the bar and another here.
 */
export type ConfigStage = {
  key: string;
  labelKey: Key;
  descriptionKey: Key;
  /** The step's number in the bar, or null for a door. */
  number: string | null;
  icon: LucideIcon | null;
};

const step = (index: number, key: string, descriptionKey: Key): ConfigStage => ({
  key,
  labelKey: STEPS[index].labelKey,
  descriptionKey,
  number: stepNumber(index),
  icon: null,
});

const door = (
  use: (typeof USES)[number],
  key: string,
  icon: LucideIcon,
  descriptionKey: Key,
): ConfigStage => ({ key, labelKey: use.labelKey, descriptionKey, number: null, icon });

export const CONFIG_STAGES: ConfigStage[] = [
  step(0, "transcription", "cfg.stage.transcription"),
  step(1, "profile", "cfg.stage.profile"),
  step(2, "graph", "cfg.stage.graph"),
  step(3, "bank", "cfg.stage.bank"),
  door(USES[0], "generation", Play, "cfg.stage.generation"),
];

/** The construction stages: a setting every one of them reads is common to the whole path. */
const CONSTRUCTION = ["transcription", "profile", "graph", "bank", "generation"];

/** The stage whose screen owns a setting, or null for one the server staged nowhere. */
export function homeOf(setting: ConfigSetting): string | null {
  return setting.stages?.[0] ?? null;
}

/** Whether a setting is read by every stage of the pipeline and so belongs to none of them. */
export function isCommon(setting: ConfigSetting): boolean {
  const stages = setting.stages ?? [];
  return CONSTRUCTION.every((stage) => stages.includes(stage));
}

/** Whether `stage` reads a setting another stage's screen owns. */
export function isSharedInto(setting: ConfigSetting, stage: string): boolean {
  const stages = setting.stages ?? [];
  return stages[0] !== stage && stages.includes(stage) && !isCommon(setting);
}
