import { Check } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import type { EvaluationRating, Usability } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ARM_META } from "./arms";

/**
 * Five questions about OUR variant, after the reveal.
 *
 * Each dimension answers to a clause the system's prompt claims to enforce — «practicar
 * no es usar» becomes `concept_fit`, self-sufficiency becomes `soundness`, context
 * variation becomes `originality`, calibration becomes `complexity`. That is what
 * connects the numbers to the design chapter instead of to a generic quality survey.
 */
const SCALES: { key: keyof EvaluationRating; label: string; question: string; ends: [string, string] }[] = [
  {
    key: "originality",
    label: "Originalidad",
    question: "¿El escenario es original, o es el típico de libro de texto?",
    ends: ["de libro de texto", "muy original"],
  },
  {
    key: "complexity",
    label: "Exigencia",
    question: "¿La exigencia encaja con el nivel del curso?",
    ends: ["trivial", "desbordado"],
  },
  {
    key: "concept_fit",
    label: "Ajuste al concepto",
    question: "¿Practica de verdad los conceptos pedidos, o solo los menciona?",
    ends: ["solo los menciona", "los practica"],
  },
  {
    key: "soundness",
    label: "Buen planteamiento",
    question: "¿Está bien planteado: autosuficiente, sin ambigüedad y resoluble?",
    ends: ["flojo", "impecable"],
  },
];

const USABILITY: { value: Usability; label: string }[] = [
  { value: "as_is", label: "Tal cual" },
  { value: "with_edits", label: "Con retoques" },
  { value: "no", label: "No" },
];

function Scale({
  value,
  onChange,
  ends,
  target,
}: {
  value: number | undefined;
  onChange: (next: number) => void;
  ends: [string, string];
  target?: number;
}) {
  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((score) => (
          <button
            key={score}
            type="button"
            onClick={() => onChange(score)}
            aria-label={`${score} de 5`}
            aria-pressed={value === score}
            className={cn(
              "h-8 flex-1 rounded-md border text-body nums transition-colors",
              value === score
                ? "border-primary bg-primary text-primary-foreground font-medium"
                : "border-border hover:bg-accent/60",
              // The target of `complexity` is 3, not 5. Marking it is the only way the
              // scale reads as "aim for the middle" instead of "more is better".
              target === score && value !== score && "border-dashed border-primary/60",
            )}
          >
            {score}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>{ends[0]}</span>
        {target ? <span className="text-primary/80">{target} = justo</span> : null}
        <span>{ends[1]}</span>
      </div>
    </div>
  );
}

export function RubricForm({
  rating,
  onSave,
  pending,
}: {
  rating: EvaluationRating | null;
  onSave: (rating: Partial<EvaluationRating>) => void;
  pending: boolean;
}) {
  const [draft, setDraft] = useState<Partial<EvaluationRating>>(rating ?? {});
  const saved = Boolean(rating);
  const patch = (fields: Partial<EvaluationRating>) => setDraft({ ...draft, ...fields });
  const complete = SCALES.every((scale) => draft[scale.key] !== undefined) && Boolean(draft.usability);

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-3 shadow-sm">
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-body font-semibold">
          Sobre la variante de{" "}
          <span style={{ color: ARM_META.system.colour }}>este sistema</span>
        </h2>
        <p className="text-small text-muted-foreground">
          Da igual cuál elegiste: esto describe lo que produjo el sistema.
        </p>
        {saved ? (
          <span className="ml-auto flex items-center gap-1 text-small text-settled">
            <Check className="size-3.5" />
            guardada
          </span>
        ) : null}
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        {SCALES.map((scale) => (
          <div key={String(scale.key)} className="space-y-1.5">
            <p className="text-small font-medium">{scale.label}</p>
            <p className="text-[11px] leading-snug text-muted-foreground">{scale.question}</p>
            <Scale
              value={draft[scale.key] as number | undefined}
              onChange={(next) => patch({ [scale.key]: next } as Partial<EvaluationRating>)}
              ends={scale.ends}
              target={scale.key === "complexity" ? 3 : undefined}
            />
          </div>
        ))}
      </div>

      <div className="space-y-1.5">
        <p className="text-small font-medium">¿Lo usarías en clase?</p>
        <div className="flex gap-1.5">
          {USABILITY.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => patch({ usability: option.value })}
              aria-pressed={draft.usability === option.value}
              className={cn(
                "h-8 flex-1 rounded-md border px-2 text-body transition-colors",
                draft.usability === option.value
                  ? "border-primary bg-primary text-primary-foreground font-medium"
                  : "border-border hover:bg-accent/60",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <Textarea
        aria-label="Qué le sobra o le falta"
        value={draft.comment ?? ""}
        onChange={(event) => patch({ comment: event.target.value })}
        placeholder="Qué le sobra o le falta (opcional)"
        className="min-h-16"
      />

      <Button className="w-full" disabled={!complete || pending} onClick={() => onSave(draft)}>
        {pending ? <Spinner /> : null}
        {saved ? "Actualizar la valoración" : "Guardar la valoración"}
      </Button>
    </section>
  );
}
