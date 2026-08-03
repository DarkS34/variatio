import { Check, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The only way to put a concept on anything.
 *
 * It is fed exclusively from the knowledge graph and has no free-text input, so a
 * concept that is not in the graph cannot be invented by hand either — the same rule
 * the tagger enforces on the LLM's output.
 */
export function ConceptPicker({
  concepts,
  selected,
  onChange,
  primary,
  onPrimaryChange,
  emptyHint = "Ningún concepto seleccionado",
  showExemplarCount = true,
  maxHeight = "18rem",
}: {
  concepts: KgConcept[];
  selected: string[];
  onChange: (next: string[]) => void;
  primary?: string | null;
  onPrimaryChange?: (next: string | null) => void;
  emptyHint?: string;
  showExemplarCount?: boolean;
  maxHeight?: string;
}) {
  const [query, setQuery] = useState("");

  const grouped = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = concepts.filter(
      (concept) =>
        concept.taggable &&
        (!needle ||
          concept.name.toLowerCase().includes(needle) ||
          concept.domain.toLowerCase().includes(needle)),
    );
    const byDomain = new Map<string, KgConcept[]>();
    for (const concept of matching) {
      const bucket = byDomain.get(concept.domain) ?? [];
      bucket.push(concept);
      byDomain.set(concept.domain, bucket);
    }
    return [...byDomain.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [concepts, query]);

  const toggle = (name: string) => {
    if (selected.includes(name)) {
      const next = selected.filter((c) => c !== name);
      onChange(next);
      if (primary === name) onPrimaryChange?.(next[0] ?? null);
    } else {
      onChange([...selected, name]);
      if (!primary) onPrimaryChange?.(name);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex min-h-8 flex-wrap items-center gap-1.5">
        {selected.length === 0 ? (
          <span className="text-sm text-muted-foreground">{emptyHint}</span>
        ) : (
          selected.map((name) => (
            <Badge
              key={name}
              variant={primary === name ? "default" : "secondary"}
              className="pr-1"
              title={primary === name ? "Concepto principal" : undefined}
            >
              {onPrimaryChange ? (
                <button
                  type="button"
                  onClick={() => onPrimaryChange(name)}
                  className="max-w-56 truncate"
                  title="Marcar como principal"
                >
                  {name}
                </button>
              ) : (
                <span className="max-w-56 truncate">{name}</span>
              )}
              <button
                type="button"
                onClick={() => toggle(name)}
                aria-label={`Quitar ${name}`}
                className="rounded-full p-0.5 hover:bg-background/60"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))
        )}
        {selected.length > 1 ? (
          <Button variant="ghost" size="sm" onClick={() => onChange([])}>
            Limpiar
          </Button>
        ) : null}
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar concepto o dominio…"
          className="pl-8"
        />
      </div>

      <div
        className="thin-scroll overflow-y-auto rounded-lg border border-border"
        style={{ maxHeight }}
      >
        {grouped.length === 0 ? (
          <p className="p-4 text-center text-sm text-muted-foreground">Sin resultados</p>
        ) : (
          grouped.map(([domain, items]) => (
            <div key={domain}>
              <div className="sticky top-0 z-10 border-b border-border bg-muted/80 px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground backdrop-blur">
                {domain}
              </div>
              {items.map((concept) => {
                const isSelected = selected.includes(concept.name);
                return (
                  <button
                    key={concept.name}
                    type="button"
                    onClick={() => toggle(concept.name)}
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors hover:bg-accent",
                      isSelected && "bg-primary/10",
                    )}
                  >
                    <span
                      className={cn(
                        "flex size-4 shrink-0 items-center justify-center rounded border",
                        isSelected ? "border-primary bg-primary text-primary-foreground" : "border-input",
                      )}
                    >
                      {isSelected ? <Check className="size-3" /> : null}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{concept.name}</span>
                    {showExemplarCount ? (
                      <span
                        className={cn(
                          "shrink-0 text-xs tabular-nums",
                          concept.exemplars === 0 ? "text-[var(--warning)]" : "text-muted-foreground",
                        )}
                        title={
                          concept.exemplars === 0
                            ? "Sin ejemplos en el banco: se generará en zero-shot"
                            : `${concept.exemplars} ejemplo(s) en el banco`
                        }
                      >
                        {concept.exemplars}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
