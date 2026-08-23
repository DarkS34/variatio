import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
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
  {
    field: "Razonamiento previo",
    naive: "el del proveedor",
    rag: "sorteado por sesión",
    system: "sorteado por sesión",
  },
];

function Cell({ value }: { value: boolean | string }) {
  if (value === true) return <span className="text-settled">sí</span>;
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
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-small font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        Qué recibe cada propuesta
      </button>
      {open ? (
        <div className="border-t border-border">
          {/* The three arms stay in the declared order — naive, rag, system — which is what
              their contrast pairs were validated on. */}
          <Table minWidth="34rem">
            <THead>
              <TR>
                <TH>Del encargo</TH>
                <TH>Comercial</TH>
                <TH>Solo RAG</TH>
                <TH>Sistema</TH>
              </TR>
            </THead>
            <TBody>
              {ROWS.map((row) => (
                <TR key={row.field}>
                  <TD>{row.field}</TD>
                  <TD>
                    <Cell value={row.naive} />
                  </TD>
                  <TD>
                    <Cell value={row.rag} />
                  </TD>
                  <TD>
                    <Cell value={row.system} />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <p className="px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
            Las tres reciben el mismo encargo y devuelven un ítem. Las dos locales usan el
            mismo modelo, así que lo que se compara son arquitecturas y no modelos. Las
            propuestas que fallan se registran como tales: no se reintenta solo la que falla.
            El razonamiento previo se sortea al empezar cada sesión y se aplica igual a las
            dos locales, de modo que nunca separa a una de la otra: queda registrado con la
            sesión para poder medir aparte si aporta algo.
          </p>
        </div>
      ) : null}
    </div>
  );
}
