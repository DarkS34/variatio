import type { EvaluationArm } from "@/lib/types";

/**
 * What each arm is, in the evaluator's words, and the colour it wears once revealed.
 *
 * The colours are the app's own state tokens, not a new palette: the system arm gets the
 * app's colour because it IS the app, the RAG baseline gets the "settled" teal, and the
 * commercial model gets a plain neutral — an outsider with no stake in the palette.
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
    colour: "var(--muted-foreground)",
    description:
      "Un modelo comercial generalista de gama gratuita, con el prompt que escribiría cualquiera con prisa: el tema, el contexto docente y las claves de salida. Ni banco ni grafo.",
  },
  rag: {
    label: "Solo RAG sobre el banco",
    short: "Solo RAG",
    colour: "var(--success)",
    description:
      "Búsqueda por similitud sobre los enunciados del banco, con los más parecidos como ejemplos. Mismo modelo local que el sistema, pero sin grafo: sin descripciones de concepto, sin prerrequisitos y sin currículo.",
  },
  system: {
    label: "Este sistema",
    short: "Sistema",
    colour: "var(--primary)",
    description:
      "El pipeline completo: ejemplos elegidos por concepto principal, prerrequisitos como andamiaje, conceptos posteriores prohibidos y el currículo como restricción dura.",
  },
};

export const POSITION_LETTERS = ["A", "B", "C"] as const;

export function letterFor(position: number): string {
  return POSITION_LETTERS[position - 1] ?? String(position);
}
