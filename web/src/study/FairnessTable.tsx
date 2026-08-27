import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";

/**
 * The contract of fairness, on screen rather than only in the plan.
 *
 * An experiment whose author designed the three conditions and has a stake in the result
 * needs its safeguards visible to whoever is judging — and to whoever reads the memoria.
 * This is the same table the code implements, kept where the evaluator can open it.
 */
const ROWS: { fieldKey: Key; naive: boolean | Key; rag: boolean | Key; system: boolean | Key }[] = [
  { fieldKey: "fair.row.concepts", naive: true, rag: true, system: true },
  { fieldKey: "fair.row.descriptions", naive: false, rag: false, system: true },
  { fieldKey: "fair.row.instructions", naive: true, rag: true, system: true },
  { fieldKey: "fair.row.decisions", naive: "fair.v.asText", rag: true, system: true },
  { fieldKey: "fair.row.context", naive: true, rag: true, system: true },
  {
    fieldKey: "fair.row.outputKeys",
    naive: "fair.v.oneLine",
    rag: "fair.v.schema",
    system: "fair.v.schemaGuide",
  },
  { fieldKey: "fair.row.noGreetings", naive: true, rag: true, system: true },
  { fieldKey: "fair.row.rules", naive: false, rag: true, system: true },
  {
    fieldKey: "fair.row.examples",
    naive: false,
    rag: "fair.v.flatCosine",
    system: "fair.v.byLabel",
  },
  { fieldKey: "fair.row.prerequisites", naive: false, rag: false, system: true },
  { fieldKey: "fair.row.curriculum", naive: false, rag: false, system: true },
  { fieldKey: "fair.row.admissibility", naive: true, rag: true, system: true },
  {
    fieldKey: "fair.row.reasoning",
    naive: "fair.v.providers",
    rag: "fair.v.drawn",
    system: "fair.v.drawn",
  },
];

function Cell({ value }: { value: boolean | Key }) {
  const { t } = useT();
  if (value === true) return <span className="text-settled">{t("fair.yes")}</span>;
  if (value === false) return <span className="text-muted-foreground/50">{t("fair.no")}</span>;
  return <span className="text-muted-foreground">{t(value)}</span>;
}

export function FairnessTable({ className }: { className?: string }) {
  const { t } = useT();
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
        {t("fair.title")}
      </button>
      {open ? (
        <div className="border-t border-border">
          {/* The three arms stay in the declared order — naive, rag, system — which is what
              their contrast pairs were validated on. */}
          <Table minWidth="34rem">
            <THead>
              <TR>
                <TH>{t("fair.col.commission")}</TH>
                <TH>{t("fair.col.naive")}</TH>
                <TH>{t("fair.col.rag")}</TH>
                <TH>{t("fair.col.system")}</TH>
              </TR>
            </THead>
            <TBody>
              {ROWS.map((row) => (
                <TR key={row.fieldKey}>
                  <TD>{t(row.fieldKey)}</TD>
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
            {t("fair.footnote")}
          </p>
        </div>
      ) : null}
    </div>
  );
}
