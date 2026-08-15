import { BookOpenText, ChevronRight, Target } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/input";
import { itemTypeOf, typeKeyOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, FewShotExemplar, ItemTypeSpec } from "@/lib/types";
import { cn } from "@/lib/utils";

import { isCodeField } from "@/features/bank/BankScreen";

function primaryText(exemplar: FewShotExemplar, spec: ItemTypeSpec | null): string {
  const value = spec ? exemplar.item[spec.primary_field] : undefined;
  return typeof value === "string" ? value.trim() : "";
}

function Exemplar({
  exemplar,
  profile,
}: {
  exemplar: FewShotExemplar;
  profile: ExemplarsProfile | null;
}) {
  const [open, setOpen] = useState(false);
  const item = exemplar.item as { item_type?: string };
  const spec = itemTypeOf(profile, item);
  const statement = primaryText(exemplar, spec);
  const concepts = (exemplar.item.concepts as string[] | undefined) ?? [];
  const primaryConcept = exemplar.item.primary_concept as string | undefined;
  const others = Object.keys(spec?.fields ?? {}).filter(
    (field) => field !== spec?.primary_field,
  );
  const showType = Object.keys(profile?.item_types ?? {}).length > 1;

  return (
    <div className="rounded-lg border border-border bg-background">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-start gap-2 px-2.5 py-2 text-left transition-colors hover:bg-accent/40"
      >
        <ChevronRight
          className={cn(
            "mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
        />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[11px] text-muted-foreground">{exemplar.id}</span>
            {showType ? (
              <Badge variant="outline">{typeLabel(profile, typeKeyOf(profile, item))}</Badge>
            ) : null}
            {primaryConcept ? (
              <Badge variant="default" className="gap-1">
                <Target />
                {primaryConcept}
              </Badge>
            ) : null}
          </span>
          <span
            className={cn(
              "mt-1 block text-xs leading-relaxed",
              open ? "whitespace-pre-wrap" : "line-clamp-2",
            )}
          >
            {statement || <span className="text-muted-foreground">(sin enunciado)</span>}
          </span>
        </span>
      </button>

      {open ? (
        <div className="animate-fade-in space-y-2 border-t border-border px-2.5 py-2">
          {others.map((field) => {
            const value = exemplar.item[field];
            if (value === null || value === undefined || value === "") return null;
            return (
              <div key={field} className="space-y-1">
                <Label>{field}</Label>
                {isCodeField(field) ? (
                  <CodeBlock code={String(value)} maxHeight="14rem" />
                ) : (
                  <p className="text-xs text-muted-foreground">{String(value)}</p>
                )}
              </div>
            );
          })}

          {concepts.length > 0 ? (
            <div className="space-y-1">
              <Label>conceptos</Label>
              <div className="flex flex-wrap gap-1">
                {concepts.map((concept) => (
                  <Badge
                    key={concept}
                    variant={concept === primaryConcept ? "default" : "outline"}
                  >
                    {concept}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function FewShotPanel({
  exemplars,
  profile,
}: {
  exemplars: FewShotExemplar[];
  profile: ExemplarsProfile | null;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        <BookOpenText className="size-3.5" />
        Ejemplares usados para el few-shot prompting
        <Badge variant={exemplars.length === 0 ? "warning" : "outline"} className="ml-auto">
          {exemplars.length === 0 ? "zero-shot" : exemplars.length}
        </Badge>
      </button>

      {open ? (
        <div className="space-y-1.5 border-t border-border p-2.5">
          {exemplars.length === 0 ? (
            <p className="text-xs text-[var(--warning)]">
              Ningún ítem del banco lleva estos conceptos: el modelo genera sin ejemplos.
            </p>
          ) : (
            exemplars.map((exemplar) => (
              <Exemplar key={exemplar.id} exemplar={exemplar} profile={profile} />
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
