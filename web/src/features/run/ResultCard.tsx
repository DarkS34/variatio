import { Brain, Check, ChevronRight, Copy, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Markdown } from "@/components/Markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/input";
import { isCodeField } from "@/features/bank/BankScreen";
import { fieldText, isEmptyField } from "@/lib/fields";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, ItemChecks, ItemTypeSpec } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";

/** A value that already fences its own code carries markdown, not raw source. */
function isFenced(value: string): boolean {
  return /^\s{0,3}(```|~~~)/m.test(value);
}

/** The one size step the app allows above `body`: a reading surface rather than dense
 *  chrome, which is what the evaluation's expanded proposal is. */
const READING = "text-[15px] leading-[1.7]";

function FieldValue({
  field,
  value,
  reading,
}: {
  field: string;
  value: string;
  reading: boolean;
}) {
  if (isCodeField(field) && !isFenced(value)) {
    return <CodeBlock code={value} maxHeight="18rem" />;
  }
  return (
    <Markdown className={cn("text-muted-foreground", reading && READING)} codeMaxHeight="18rem">
      {value}
    </Markdown>
  );
}

/**
 * The fields of one item, in the order the profile declares them.
 *
 * Shared with the evaluation's proposal cards so the three arms are rendered by the same
 * code: a comparison where one card lays its fields out differently is measuring layout.
 * `reading` steps the prose up one size and nothing else — the order and the labels are
 * the same, so the expanded view is the card at a size a person can read, not a fourth
 * rendering.
 */
export function ItemFields({
  item,
  spec,
  reading = false,
}: {
  item: Record<string, unknown>;
  spec: ItemTypeSpec | null;
  reading?: boolean;
}) {
  const primary = spec ? fieldText(item[spec.primary_field]) : "";
  const others = Object.keys(spec?.fields ?? {}).filter((f) => f !== spec?.primary_field);

  return (
    <>
      <Markdown className={cn(reading && READING)}>{primary}</Markdown>
      {others.map((field) => {
        const value = item[field];
        if (isEmptyField(value)) return null;
        return (
          <div key={field} className="space-y-1">
            <Label>{spec?.fields?.[field]?.label || field}</Label>
            <FieldValue field={field} value={fieldText(value)} reading={reading} />
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
export function ItemChecks({ checks, retried }: { checks?: ItemChecks | null; retried?: number }) {
  const { t } = useT();
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
        {retried ? (
          <span>
            <Badge variant="outline">{t("result.retried", { n: retried })}</Badge>
          </span>
        ) : null}
        {flagged ? (
          checks.flags.map((flag) => <span key={flag}>{flag}</span>)
        ) : (
          <span>{t("result.noFlags")}</span>
        )}
        <span className="text-micro text-muted-foreground">
          {tagger
            ? t("result.taggedAs", { concept: tagger.primary ?? t("common.none").toLowerCase() })
            : t("result.noTagger")}
          {checks.similarity
            ? ` ${t("result.closestTo", {
                to: checks.similarity.to,
                score: checks.similarity.score.toFixed(2),
              })}`
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
  retried,
  profile,
  saved,
}: {
  index: number;
  item: Record<string, unknown>;
  itemType?: string;
  thinking?: string | null;
  checks?: ItemChecks | null;
  retried?: number;
  profile: ExemplarsProfile;
  /** Whether the server has already kept this item as a row of «Mis variantes». */
  saved?: boolean;
}) {
  const { t, language } = useT();
  const [showThinking, setShowThinking] = useState(false);
  const spec = itemTypeOf(profile, { item_type: itemType });
  const manyTypes = Object.keys(profile.item_types).length > 1;

  return (
    <Card className="animate-fade-in">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <CardTitle>{t("result.itemHeading", { n: index })}</CardTitle>
          {manyTypes ? (
            <span className="text-small text-muted-foreground">
              {typeLabel(profile, itemType ?? null, t)}
            </span>
          ) : null}
          {saved ? (
            <Badge variant="secondary" className="gap-1">
              <Check className="size-3" />
              {t("result.saved")}
            </Badge>
          ) : null}
          <div className="ml-auto flex gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("generations.copyJson")}
              onClick={() => navigator.clipboard.writeText(JSON.stringify(item, null, 2))}
            >
              <Copy />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ItemFields item={item} spec={spec} />
        <ItemChecks checks={checks} retried={retried} />

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
              {t("result.reasoning")}
              <span className="ml-auto nums">
                {thinking.length.toLocaleString(language)}
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
  t: (key: Key, params?: Record<string, string | number>) => string,
): string {
  const lines: string[] = [t("result.generatedItems"), ""];
  items.forEach(({ item, item_type }, index) => {
    const spec = itemTypeOf(profile, { item_type });
    const heading = t("result.itemN", { n: index + 1 });
    lines.push(
      Object.keys(profile.item_types).length > 1
        ? `${heading} · ${typeLabel(profile, item_type ?? null, t)}`
        : heading,
      "",
      spec ? fieldText(item[spec.primary_field]) : "",
      "",
    );
    for (const field of Object.keys(spec?.fields ?? {})) {
      if (field === spec?.primary_field) continue;
      const value = item[field];
      if (isEmptyField(value)) continue;
      const text = fieldText(value);
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
