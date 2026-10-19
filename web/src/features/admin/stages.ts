import { MessageCircle, MessagesSquare, Play, Scale, type LucideIcon } from "lucide-react";

import type { Key } from "@/lib/i18n";
import { STEPS, USES, stepNumber, type Door } from "@/lib/steps";
import type { ConfigSetting, FeatureName, GatedName } from "@/lib/types";

/**
 * THE CONFIGURATION'S SCREENS ARE THE PATH'S STAGES, named and numbered as the bar names
 * and numbers them: the construction steps carry their number, the doors their icon.
 *
 * The keys are the server's (`variatio.settings.types.STAGES` plus the study's and the
 * tutor's), matched against what `/api/admin/config` sends; the labels come from
 * `lib/steps.ts`, the one home of the path, so a stage cannot be called one thing in the
 * bar and another here.
 *
 * The stage of a door — generating, the evaluation, the tutor, the free chat — is drawn in
 * «Funciones», beside who may use it where it is an optional function, and «Configuración»
 * lists the construction's: `door` says which.
 */
export type ConfigStage = {
  key: string;
  labelKey: Key;
  descriptionKey: Key;
  /** The step's number in the bar, or null for a door. */
  number: string | null;
  icon: LucideIcon | null;
  /** The door whose stage this is, or null for a construction step. */
  door: Door["key"] | null;
  /** The optional function whose door this is, or null for the product's own stages. */
  feature: FeatureName | null;
  /** The name the users of the door's function are chosen under, or null for a step. */
  access: GatedName | null;
};

const step = (index: number, key: string, descriptionKey: Key): ConfigStage => ({
  key,
  labelKey: STEPS[index].labelKey,
  descriptionKey,
  number: stepNumber(index),
  icon: null,
  door: null,
  feature: null,
  access: null,
});

/**
 * A door's screen, found in `USES` by the door's key and never by its position: the bar
 * draws a subset of the list per account, so an index names no fixed door. Every door has
 * a screen whatever its function's mode, drawn in «Funciones», where the administrator
 * configures a function before opening it to anybody.
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
    door: use,
    feature: entry.feature,
    access: entry.access,
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
  door("chat", "chat", MessageCircle, "cfg.stage.chat"),
];

/** The stage «Funciones» draws for a door, by the door's key. */
export function stageOfDoor(door: Door["key"]): ConfigStage {
  return CONFIG_STAGES.find((stage) => stage.door === door)!;
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
