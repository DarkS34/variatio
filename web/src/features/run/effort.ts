export type EffortLevel = "low" | "medium" | "high" | "max";

export const EFFORT_ORDER: EffortLevel[] = ["low", "medium", "high", "max"];

export const EFFORT_LABELS: Record<EffortLevel, string> = {
  low: "Bajo",
  medium: "Medio",
  high: "Alto",
  max: "Máximo",
};

export interface EffortPolicy {
  /** Matched against the start of the resolved generation model's name. */
  match: string;
  levels: EffortLevel[];
  /** Choosing a level ABOVE this one shows `warning`. */
  warnAbove?: EffortLevel;
  warning?: string;
  /** Always-visible nuance for this model, warning or not. */
  note?: string;
}

// To support another generation model, add its entry here: which levels it accepts,
// and what (if anything) the screen should warn about. First prefix match wins.
export const EFFORT_POLICIES: EffortPolicy[] = [
  {
    match: "qwen3.8",
    levels: ["low", "medium", "high", "max"],
    warnAbove: "medium",
    warning:
      "Por encima de «Medio», qwen3.8 delibera durante miles de palabras en la GPU local: cada ítem puede tardar muchos minutos, y en el nivel alto se ha medido que llega a devolver una respuesta vacía.",
  },
  {
    match: "gemma-4",
    levels: ["low", "medium", "high"],
    note: "Servido por Cerebras: responde en segundos con cualquier nivel, y en la práctica los tres se comportan casi igual.",
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

export function effortWarning(level: EffortLevel, policy: EffortPolicy): string | null {
  if (!policy.warnAbove || !policy.warning) return null;
  return EFFORT_ORDER.indexOf(level) > EFFORT_ORDER.indexOf(policy.warnAbove)
    ? policy.warning
    : null;
}
