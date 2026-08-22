import { Brain, ChevronRight, Copy, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/input";
import { isCodeField } from "@/features/bank/BankScreen";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, ItemChecks, ItemTypeSpec } from "@/lib/types";
import { cn } from "@/lib/utils";

/** A value that already fences its own code carries markdown, not raw source. */
function isFenced(value: string): boolean {
  return /^\s{0,3}(```|~~~)/m.test(value);
}

function FieldValue({ field, value }: { field: string; value: string }) {
  if (isCodeField(field) && !isFenced(value)) {
    return <CodeBlock code={value} maxHeight="18rem" />;
  }
  return <Markdown className="text-muted-foreground" codeMaxHeight="18rem">{value}</Markdown>;
}

/**
 * The fields of one item, in the order the profile declares them.
 *
 * Shared with the evaluation's proposal cards so the three arms are rendered by the same
 * code: a comparison where one card lays its fields out differently is measuring layout.
 */
export function ItemFields({
  item,
  spec,
}: {
  item: Record<string, unknown>;
  spec: ItemTypeSpec | null;
}) {
  const primary = spec ? String(item[spec.primary_field] ?? "") : "";
  const others = Object.keys(spec?.fields ?? {}).filter((f) => f !== spec?.primary_field);

  return (
    <>
      <Markdown>{primary}</Markdown>
      {others.map((field) => {
        const value = item[field];
        if (value === null || value === undefined || value === "") return null;
        return (
          <div key={field} className="space-y-1">
            <Label>{field}</Label>
            <FieldValue field={field} value={String(value)} />
          </div>
        );
      })}
    </>
  );
}

/**
 * What the pipeline could verify about a variant after writing it. None of it rejects:
 * the schema already did that, and what is left — a forbidden concept named, a near
 * copy, the tagger not recognising the objective — are signals for the person reading.
 */
export function ItemChecks({ checks }: { checks?: ItemChecks | null }) {
  if (!checks) return null;
  const flagged = checks.flags.length > 0;
  const tagger = checks.tagger;
  return (
    <div
      className={cn(
        "flex flex-wrap items-start gap-x-3 gap-y-1 rounded-lg border px-3 py-2 text-small",
        flagged ? "border-attention/40 text-attention" : "border-border text-muted-foreground",
      )}
    >
      {flagged ? <ShieldAlert className="mt-0.5 size-3.5 shrink-0" /> : <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {flagged ? (
          checks.flags.map((flag) => <span key={flag}>{flag}</span>)
        ) : (
          <span>Sin señales: el etiquetador la reconoce, nada prohibido, escenario propio.</span>
        )}
        <span className="text-micro text-muted-foreground">
          {tagger ? `etiquetada como ${tagger.primary ?? "nada"}` : "sin etiquetador"}
          {checks.similarity
            ? ` · más cercana a ${checks.similarity.to} (${checks.similarity.score.toFixed(2)})`
            : ""}
        </span>
      </div>
    </div>
  );
}

export function ResultCard({
  index,
  item,
  itemType,
  thinking,
  checks,
  profile,
}: {
  index: number;
  item: Record<string, unknown>;
  itemType?: string;
  thinking?: string | null;
  checks?: ItemChecks | null;
  profile: ExemplarsProfile;
}) {
  const [showThinking, setShowThinking] = useState(false);
  const spec = itemTypeOf(profile, { item_type: itemType });
  const manyTypes = Object.keys(profile.item_types).length > 1;

  return (
    <Card className="animate-fade-in">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <CardTitle>Ítem {index}</CardTitle>
          {manyTypes ? (
            <span className="text-small text-muted-foreground">
              {typeLabel(profile, itemType ?? null)}
            </span>
          ) : null}
          <div className="ml-auto flex gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Copiar JSON"
              onClick={() => navigator.clipboard.writeText(JSON.stringify(item, null, 2))}
            >
              <Copy />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ItemFields item={item} spec={spec} />
        <ItemChecks checks={checks} />

        {thinking ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <button
              type="button"
              onClick={() => setShowThinking((v) => !v)}
              aria-expanded={showThinking}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-small font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <ChevronRight
                className={cn("size-3.5 transition-transform", showThinking && "rotate-90")}
              />
              <Brain className="size-3.5" />
              Razonamiento
              <span className="ml-auto nums">
                {thinking.length.toLocaleString("es-ES")}
              </span>
            </button>
            {showThinking ? (
              <pre className="thin-scroll max-h-56 overflow-auto border-t border-border bg-muted/30 p-3 font-mono text-small leading-relaxed whitespace-pre-wrap text-muted-foreground">
                {thinking}
              </pre>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function toMarkdown(
  items: { item: Record<string, unknown>; item_type?: string }[],
  profile: ExemplarsProfile,
): string {
  const lines: string[] = ["# Ítems generados", ""];
  items.forEach(({ item, item_type }, index) => {
    const spec = itemTypeOf(profile, { item_type });
    const heading = `## Ítem ${index + 1}`;
    lines.push(
      Object.keys(profile.item_types).length > 1
        ? `${heading} · ${typeLabel(profile, item_type ?? null)}`
        : heading,
      "",
      spec ? String(item[spec.primary_field] ?? "") : "",
      "",
    );
    for (const field of Object.keys(spec?.fields ?? {})) {
      if (field === spec?.primary_field) continue;
      const value = item[field];
      if (value === null || value === undefined || value === "") continue;
      const text = String(value);
      // Fencing something that already fences itself nests the blocks and breaks both.
      const fence = isCodeField(field) && !isFenced(text);
      lines.push(`### ${field}`, "");
      lines.push(fence ? "```" : "", text, fence ? "```" : "", "");
    }
  });
  return lines.join("\n");
}

export function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}
