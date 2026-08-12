import { Copy } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/input";
import { isCodeField } from "@/features/bank/BankScreen";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ContentProfile } from "@/lib/types";

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
  profile: ContentProfile;
}) {
  const [showThinking, setShowThinking] = useState(false);
  const spec = itemTypeOf(profile, { item_type: itemType });
  const primary = spec ? String(item[spec.primary_field] ?? "") : "";
  const others = Object.keys(spec?.fields ?? {}).filter((f) => f !== spec?.primary_field);
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
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{primary}</p>

        {others.map((field) => {
          const value = item[field];
          if (value === null || value === undefined || value === "") return null;
          return (
            <div key={field} className="space-y-1">
              <Label>{field}</Label>
              {isCodeField(field) ? (
                <CodeBlock code={String(value)} maxHeight="18rem" />
              ) : (
                <p className="text-sm text-muted-foreground">{String(value)}</p>
              )}
            </div>
          );
        })}

        {thinking ? (
          <div>
            <Button variant="ghost" size="sm" onClick={() => setShowThinking((v) => !v)}>
              {showThinking ? "Ocultar" : "Ver"} razonamiento
            </Button>
            {showThinking ? (
              <pre className="thin-scroll mt-2 max-h-56 overflow-auto rounded-md border border-border p-2 font-mono text-xs whitespace-pre-wrap text-muted-foreground">
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
  profile: ContentProfile,
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
      lines.push(`### ${field}`, "");
      lines.push(
        isCodeField(field) ? "```" : "",
        String(value),
        isCodeField(field) ? "```" : "",
        "",
      );
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
