import type { EvaluationArm } from "@/lib/types";

/**
 * What each arm is, in the evaluator's words, and the colour it wears once revealed.
 *
 * The colours are `--arm-*`, the app's only categorical scale, and they are measured
 * rather than chosen — see the note beside them in `index.css`. They used to borrow the
 * state tokens (muted-foreground, success, primary), which told a nice story — the system
 * wearing the app's own colour, the commercial model a neutral outsider — and failed as an
 * encoding: gray against teal is ΔE 7.5 in normal vision, half the readable floor.
 *
 * `ARMS` order is also the order the palette was validated on, so anything that draws the
 * three arms side by side draws them in it.
 *
 * They appear ONLY after the reveal. Before it the three cards are deliberately
 * colourless, because a card wearing a colour is a card carrying information.
 */
export const ARM_META: Record<
  EvaluationArm,
  { label: string; short: string; colour: string; description: string }
> = {
  naive: {
    label: "Modelo comercial",
    short: "Comercial",
    colour: "var(--arm-naive)",
    description:
      "Un modelo comercial generalista de gama gratuita, con el prompt que escribiría cualquiera con prisa: el tema, el contexto docente y las claves de salida. Ni banco ni grafo.",
  },
  rag: {
    label: "Solo RAG sobre el banco",
    short: "Solo RAG",
    colour: "var(--arm-rag)",
    description:
      "Búsqueda por similitud sobre los enunciados del banco, con los más parecidos como ejemplos. Mismo modelo local que el sistema, pero sin grafo: sin descripciones de concepto, sin prerrequisitos y sin currículo.",
  },
  system: {
    label: "Este sistema",
    short: "Sistema",
    colour: "var(--arm-system)",
    description:
      "El pipeline completo: ejemplos elegidos por concepto principal, prerrequisitos como andamiaje, conceptos posteriores prohibidos y el currículo como restricción dura.",
  },
};

export const POSITION_LETTERS = ["A", "B", "C"] as const;

export function letterFor(position: number): string {
  return POSITION_LETTERS[position - 1] ?? String(position);
}
