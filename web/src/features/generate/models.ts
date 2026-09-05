import type { Key } from "@/lib/i18n";

import type { EffortLevel } from "./effort";

/**
 * What the screen knows about each model it may offer to write a variant.
 *
 * WHICH models are offered is the installation's (`generation.models`, «Configuración →
 * Modelos generadores»); this table is what turns one of those names into something a person
 * can choose between — a name, a link to read the rest, and the effort levels that model
 * actually accepts.
 *
 * Keyed by the START of the model name and not by the whole of it, because a family is
 * served under several names: `qwen3.8:27b-q8_0` locally and `qwen3.8:27b-q5_K_M` on
 * another installation are the same choice with the same trade-off. A model no entry
 * matches is offered all the same, with its bare name alone — a catalogue that
 * refused what it does not recognise would make adding a model a code change.
 */
export interface ModelFamily {
  /** Matched against the start of the resolved model's name. First match wins. */
  match: string;
  /** What it is called on screen: the family, never the quantisation tag. */
  label: string;
  /** Where the model itself is documented — Ollama's library, or its weights. */
  url: string | null;
  /** Drives the icon beside the name; nothing else reads it. */
  speed: "fast" | "slow" | null;
  levels: EffortLevel[];
  /** Choosing a level ABOVE this one shows `warningKey`. */
  warnAbove?: EffortLevel;
  warningKey?: Key;
}

/*
 * WHETHER THE SLIDER IS DRAWN AT ALL IS NOT HERE ANY MORE (2026-09-01, explicit user
 * request). It was `effortMatters`, a field of the family: `false` meant «this one accepts
 * the levels and ignores them», measured on `gemma-4`, and declaring it for a new model was
 * a code change and a deploy. It is `generation.fixed_effort` now, an engine-scoped list in
 * «Configuración → Modelos generadores» that reaches the browser through `/api/health`.
 *
 * `levels` stayed, and the split is the point: what a model ACCEPTS is what `clampEffort`
 * needs in order to send a valid value, and sending an invalid one is a 400 rather than a
 * matter of taste. What a model DOES with what it accepts is the measurement, and that is
 * the administrator's to record.
 */

// To offer another model, add its family here and put its name in «Modelos generadores».
export const MODEL_FAMILIES: ModelFamily[] = [
  {
    match: "qwen3.8",
    label: "Qwen3.8 (local)", // i18n-exempt
    url: "https://huggingface.co/Qwen/Qwen3.8-27B",
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
    label: "Gemma 4 (Cerebras)", // i18n-exempt
    url: "https://huggingface.co/google/gemma-4-31B-it",
    speed: "fast",
    // Measured: on this family the three levels answer the same, which is why it is the
    // one name «Modelos generadores» ships in `generation.fixed_effort`. The switch stays
    // there — reasoning on or off is a real choice, and it is what the run records.
    levels: ["low", "medium", "high"],
  },
  /*
   * THE OTHER HALF OF EACH FAMILY (2026-09-04, explicit user request). Both families are
   * served on BOTH engines under different names — `qwen-3.8-27b` is Cerebras' id for what
   * Ollama calls `qwen3.8:27b-q8_0`, and `gemma4:31b-it-q4_K_M` is Ollama's for what
   * Cerebras calls `gemma-4-31b` — and on `cerebras+ollama` an installation may offer all
   * four at once. Until now the two absent halves fell through to the unknown family, so
   * they were listed by their bare id rather than by the family's own name, which is
   * exactly the state this table exists to fix.
   *
   * The prefixes cannot collide: `qwen3.8` and `qwen-3.8` differ at the fifth character,
   * `gemma-4` and `gemma4` at the sixth. The LABEL now says which engine serves each,
   * because that is the whole difference between a family's two halves and the raw name is
   * not always beside it.
   */
  {
    match: "qwen-3.8",
    label: "Qwen3.8 (Cerebras)", // i18n-exempt
    url: "https://huggingface.co/Qwen/Qwen3.8-27B",
    speed: "fast",
    // Three, because Cerebras has no `max` at all and floors it at `high` — the same
    // ceiling the local half reaches for a different reason. NO WARNING: what
    // `effort.warn.qwen38` reports was measured on Ollama and is about the local GPU
    // («devuelve una respuesta vacía» at `high`), so repeating it here would be quoting a
    // measurement of another serving stack. This half is unmeasured at every level.
    levels: ["low", "medium", "high"],
  },
  {
    match: "gemma4",
    label: "Gemma 4 (local)", // i18n-exempt
    url: "https://ollama.com/library/gemma4",
    speed: "slow",
    // Declared, not measured. The «los tres niveles responden igual» of the Cerebras half
    // was measured against Cerebras and says nothing about Ollama's renderer, so the three
    // stops are drawn and none is locked; `max` is left out because nothing has been seen
    // to implement it and a stop that changes nothing is a stop that lies.
    levels: ["low", "medium", "high"],
  },
];

const UNKNOWN: ModelFamily = {
  match: "",
  label: "",
  url: null,
  speed: null,
  // An unrecognised model is offered whole, slider included: refusing a control because
  // nobody has measured the model yet would make adding one a code change. Measure it and
  // the answer goes in `generation.fixed_effort`, not here.
  levels: ["low", "medium", "high", "max"],
};

/** The family a model belongs to; an unrecognised one keeps its own name. */
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
