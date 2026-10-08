import { MessagesSquare, Play, Scale, type LucideIcon } from "lucide-react";

import type { Key } from "@/lib/i18n";
import { STEPS, USES, stepNumber, type Door } from "@/lib/steps";
import type { ConfigSetting, FeatureName } from "@/lib/types";

/**
 * THE CONFIGURATION'S SCREENS ARE THE PATH'S STAGES, named and numbered as the bar names
 * and numbers them: the construction steps carry their number, the doors their icon.
 *
 * The keys are the server's (`variatio.settings.types.STAGES` plus the study's and the
 * tutor's), matched against what `/api/admin/config` sends; the labels come from
 * `lib/steps.ts`, the one home of the path, so a stage cannot be called one thing in the
 * bar and another here.
 *
 * The stage of an optional function is drawn in that function's own tab of «Administración»,
 * beside who may use it, and «Configuración» lists the others: `feature` says which.
 */
export type ConfigStage = {
  key: string;
  labelKey: Key;
  descriptionKey: Key;
  /** The step's number in the bar, or null for a door. */
  number: string | null;
  icon: LucideIcon | null;
  /** The optional function whose door this is, or null for the product's own stages. */
  feature: FeatureName | null;
};

const step = (index: number, key: string, descriptionKey: Key): ConfigStage => ({
  key,
  labelKey: STEPS[index].labelKey,
  descriptionKey,
  number: stepNumber(index),
  icon: null,
  feature: null,
});

/**
 * A door's screen, found in `USES` by the door's key and never by its position: the bar
 * draws a subset of the list per account, so an index names no fixed door. Every door has
 * a screen whatever its function's mode — an optional function's is drawn in its own tab,
 * where the administrator configures it before opening it to anybody.
 */
const door = (
  use: Door["key"],
  key: string,
  icon: LucideIcon,
  descriptionKey: Key,
): ConfigStage => {
  const entry = USES.find((candidate) => candidate.key === use)!;
  return {
    key,
    labelKey: entry.labelKey,
    descriptionKey,
    number: null,
    icon,
    feature: entry.feature,
  };
};

export const CONFIG_STAGES: ConfigStage[] = [
  step(0, "transcription", "cfg.stage.transcription"),
  step(1, "graph", "cfg.stage.graph"),
  // The types of exercise are the first part of the bank's step since 2026-10-08, and their
  // settings with them: one screen per step, as the bar draws the path.
  step(2, "bank", "cfg.stage.bank"),
  door("generate", "generation", Play, "cfg.stage.generation"),
  door("compare", "evaluation", Scale, "cfg.stage.evaluation"),
  door("tutor", "tutoring", MessagesSquare, "cfg.stage.tutoring"),
];

/** The stage an optional function's tab draws, by the function's name. */
export function stageOfFeature(feature: FeatureName): ConfigStage {
  return CONFIG_STAGES.find((stage) => stage.feature === feature)!;
}

/** The construction stages: a setting every one of them reads is common to the whole path. */
const CONSTRUCTION = ["transcription", "graph", "bank", "generation"];

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
