import { Brain, ChevronRight, Copy } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/input";
import { isCodeField } from "@/features/bank/BankScreen";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, ItemTypeSpec } from "@/lib/types";
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

export function ResultCard({
  index,
  item,
  itemType,
  thinking,
  profile,
}: {
  index: number;
  item: Record<string, unknown>;
  itemType?: string;
  thinking?: string | null;
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
            <span className="text-xs text-muted-foreground">
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

        {thinking ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <button
              type="button"
              onClick={() => setShowThinking((v) => !v)}
              aria-expanded={showThinking}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <ChevronRight
                className={cn("size-3.5 transition-transform", showThinking && "rotate-90")}
              />
              <Brain className="size-3.5" />
              Razonamiento
              <span className="ml-auto tabular-nums">
                {thinking.length.toLocaleString("es-ES")}
              </span>
            </button>
            {showThinking ? (
              <pre className="thin-scroll max-h-56 overflow-auto border-t border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">
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
