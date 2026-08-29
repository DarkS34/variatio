import type { Key } from "@/lib/i18n";

import type { EffortLevel } from "./effort";

/**
 * What the screen knows about each model it may offer to write a variant.
 *
 * WHICH models are offered is the installation's (`generation.models`, «Configuración →
 * Modelos ofrecidos»); this table is what turns one of those names into something a person
 * can choose between — a name, one sentence about what the choice costs, a link to read
 * the rest, and the effort levels that model actually accepts.
 *
 * Keyed by the START of the model name and not by the whole of it, because a family is
 * served under several names: `qwen3.8:27b-q8_0` locally and `qwen3.8:27b-q4_K_M` on
 * another installation are the same choice with the same trade-off. A model no entry
 * matches is offered all the same, with its bare name and no note — a catalogue that
 * refused what it does not recognise would make adding a model a code change.
 */
export interface ModelFamily {
  /** Matched against the start of the resolved model's name. First match wins. */
  match: string;
  /** What it is called on screen: the family, never the quantisation tag. */
  label: string;
  /** Where the model itself is documented — Ollama's library, or its weights. */
  url: string | null;
  /** The one sentence somebody needs in order to choose. */
  blurbKey: Key | null;
  /** Drives the icon beside the name; nothing else reads it. */
  speed: "fast" | "slow" | null;
  levels: EffortLevel[];
  /** Choosing a level ABOVE this one shows `warningKey`. */
  warnAbove?: EffortLevel;
  warningKey?: Key;
  /** Always-visible nuance about this model's effort levels, warning or not. */
  noteKey?: Key;
}

// To offer another model, add its family here and put its name in «Modelos ofrecidos».
export const MODEL_FAMILIES: ModelFamily[] = [
  {
    match: "qwen3.8",
    label: "Qwen3.8", // i18n-exempt
    url: "https://ollama.com/library/qwen3.8:27b-q8_0",
    blurbKey: "model.blurb.qwen38",
    speed: "slow",
    // THREE and not four: `max` is not a level of this model, it is `high` under another
    // name. Measured 2026-08-29 against Ollama 0.32.13 on `qwen3.8:27b-q8_0`, temperature 0
    // and a fixed seed — `high` and `max` render the same 56-token prompt and return a
    // byte-identical answer, where `low` is 44 and `medium` is 14, the model's own default.
    // A fourth stop that cannot change anything is a stop that lies.
    levels: ["low", "medium", "high"],
    warnAbove: "medium",
    warningKey: "effort.warn.qwen38",
  },
  {
    match: "gemma-4",
    label: "Gemma 4", // i18n-exempt
    url: "https://huggingface.co/google/gemma-4-31B-it",
    blurbKey: "model.blurb.gemma4",
    speed: "fast",
    levels: ["low", "medium", "high"],
    noteKey: "effort.note.gemma4",
  },
];

const UNKNOWN: ModelFamily = {
  match: "",
  label: "",
  url: null,
  blurbKey: null,
  speed: null,
  levels: ["low", "medium", "high", "max"],
};

/** The family a model belongs to; an unrecognised one keeps its own name and no note. */
export function familyOf(model: string | undefined): ModelFamily {
  if (!model) return UNKNOWN;
  return (
    MODEL_FAMILIES.find((family) => model.startsWith(family.match)) ?? {
      ...UNKNOWN,
      label: model,
    }
  );
}

/** What to call a model on screen: its family's name, or the raw name if none matches. */
export function modelLabel(model: string | undefined): string {
  return familyOf(model).label || (model ?? "");
}
