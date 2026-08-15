import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * The contract of fairness, on screen rather than only in the plan.
 *
 * An experiment whose author designed the three conditions and has a stake in the result
 * needs its safeguards visible to whoever is judging — and to whoever reads the memoria.
 * This is the same table the code implements, kept where the evaluator can open it.
 */
const ROWS: { field: string; naive: boolean | string; rag: boolean | string; system: boolean | string }[] = [
  { field: "Conceptos objetivo (los nombres)", naive: true, rag: true, system: true },
  { field: "Descripciones de esos conceptos", naive: false, rag: false, system: true },
  { field: "Instrucciones adicionales", naive: true, rag: true, system: true },
  { field: "Decisiones de campo", naive: "como texto", rag: true, system: true },
  { field: "Contexto docente del perfil", naive: true, rag: true, system: true },
  { field: "Claves de salida", naive: "una línea", rag: "schema", system: "schema + guía" },
  { field: "Prohibición de saludos y meta-texto", naive: true, rag: true, system: true },
  { field: "Reglas de redacción de la asignatura", naive: false, rag: true, system: true },
  { field: "Ejemplos del banco", naive: false, rag: "coseno plano", system: "por etiqueta" },
  { field: "Prerrequisitos y posteriores", naive: false, rag: false, system: true },
  { field: "Currículo cubierto", naive: false, rag: false, system: true },
  { field: "Revisión de las instrucciones", naive: true, rag: true, system: true },
];

function Cell({ value }: { value: boolean | string }) {
  if (value === true) return <span className="text-[var(--success)]">sí</span>;
  if (value === false) return <span className="text-muted-foreground/50">no</span>;
  return <span className="text-muted-foreground">{value}</span>;
}

export function FairnessTable({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={cn("overflow-hidden rounded-lg border border-border", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        Qué recibe cada propuesta
      </button>
      {open ? (
        <div className="thin-scroll overflow-x-auto border-t border-border">
          <table className="w-full min-w-[34rem] text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Del encargo</th>
                <th className="px-3 py-2 text-left font-medium">Comercial</th>
                <th className="px-3 py-2 text-left font-medium">Solo RAG</th>
                <th className="px-3 py-2 text-left font-medium">Sistema</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row) => (
                <tr key={row.field} className="border-b border-border/50 last:border-0">
                  <td className="px-3 py-1.5">{row.field}</td>
                  <td className="px-3 py-1.5">
                    <Cell value={row.naive} />
                  </td>
                  <td className="px-3 py-1.5">
                    <Cell value={row.rag} />
                  </td>
                  <td className="px-3 py-1.5">
                    <Cell value={row.system} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
            Las tres reciben el mismo encargo y devuelven un ítem. Las dos locales usan el
            mismo modelo, así que lo que se compara son arquitecturas y no modelos. Las
            propuestas que fallan se registran como tales: no se reintenta solo la que falla.
          </p>
        </div>
      ) : null}
    </div>
  );
}
