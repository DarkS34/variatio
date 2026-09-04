import { ChevronRight, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { hasExemplars } from "@/lib/concepts";
import { domainColours } from "@/lib/domains";
import type { KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

/**
 * The embedded picker: it puts concepts on ONE item, and marks which of them is the
 * primary — the thing the item makes the student practise. `ConceptSelector` is a
 * full-screen overlay for choosing a set and has no notion of a primary, so it does not
 * replace this.
 *
 * It is fed exclusively from the knowledge graph and has no free-text input, so a
 * concept that is not in the graph cannot be invented by hand either — the same rule
 * the tagger enforces on the LLM's output.
 *
 * Concepts are drawn as chips inside collapsible domains rather than one row each: a
 * curriculum is a couple of hundred names, and a flat list of them says nothing about
 * how they are grouped or how much of a domain is already chosen. The domain dot uses
 * the same palette as the graph viewer, so a domain is the same colour on both screens.
 */

const MAX_VISIBLE_CHIPS = 14;

export function ConceptPicker({
  concepts,
  selected,
  onChange,
  primary,
  onPrimaryChange,
  emptyHint,
  showExemplarCount = true,
  onlyWithExemplars = false,
  maxHeight = "18rem",
  disabled = false,
}: {
  concepts: KgConcept[];
  selected: string[];
  onChange: (next: string[]) => void;
  primary?: string | null;
  onPrimaryChange?: (next: string | null) => void;
  emptyHint?: string;
  showExemplarCount?: boolean;
  onlyWithExemplars?: boolean;
  maxHeight?: string;
  disabled?: boolean;
}) {
  const { t, plural } = useT();
  const emptyText = emptyHint ?? t("concept.noneSelected");
  const [query, setQuery] = useState("");
  const [override, setOverride] = useState<Record<string, boolean>>({});
  const [showAllSelected, setShowAllSelected] = useState(false);

  const colours = useMemo(() => domainColours(concepts), [concepts]);
  const domainOf = useMemo(
    () => new Map(concepts.map((concept) => [concept.name, concept.domain])),
    [concepts],
  );
  const chosen = useMemo(() => new Set(selected), [selected]);
  const searching = query.trim().length > 0;
  const visible = showAllSelected ? selected : selected.slice(0, MAX_VISIBLE_CHIPS);

  const grouped = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = concepts.filter(
      (concept) =>
        concept.taggable &&
        // Something already chosen stays visible even when it does not pass the filter,
        // or it would vanish from the list while still counting as selected.
        (!onlyWithExemplars || hasExemplars(concept) || chosen.has(concept.name)) &&
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
    return [...byDomain.entries()];
  }, [concepts, query, onlyWithExemplars, chosen]);

  const toggle = (name: string) => {
    if (chosen.has(name)) {
      const next = selected.filter((c) => c !== name);
      onChange(next);
      if (primary === name) onPrimaryChange?.(next[0] ?? null);
    } else {
      onChange([...selected, name]);
      if (!primary) onPrimaryChange?.(name);
    }
  };

  const toggleDomain = (items: KgConcept[], allChosen: boolean) => {
    const names = items.map((concept) => concept.name);
    if (allChosen) {
      const next = selected.filter((c) => !names.includes(c));
      onChange(next);
      if (primary && names.includes(primary)) onPrimaryChange?.(next[0] ?? null);
    } else {
      const next = [...selected, ...names.filter((name) => !chosen.has(name))];
      onChange(next);
      if (!primary) onPrimaryChange?.(next[0] ?? null);
    }
  };

  const setAll = (open: boolean) =>
    setOverride(Object.fromEntries(grouped.map(([domain]) => [domain, open])));

  const anyOpen = grouped.some(
    ([domain, items]) =>
      override[domain] ?? (searching || items.some((concept) => chosen.has(concept.name))),
  );

  return (
    <div className="space-y-2">
      <div className="flex min-h-8 flex-wrap items-center gap-1.5">
        {selected.length === 0 ? (
          <span className="text-body text-muted-foreground">{emptyText}</span>
        ) : (
          visible.map((name) => (
            <Badge
              key={name}
              variant={primary === name ? "default" : "secondary"}
              className="pr-1"
              title={primary === name ? t("concept.isPrimary") : undefined}
            >
              <span
                className="size-1.5 shrink-0 rounded-full"
                style={{ background: colours.get(domainOf.get(name) ?? "") }}
              />
              {onPrimaryChange && !disabled ? (
                <button
                  type="button"
                  onClick={() => onPrimaryChange(name)}
                  className="max-w-56 truncate"
                  title={t("concept.markPrimary")}
                >
                  {name}
                </button>
              ) : (
                <span className="max-w-56 truncate">{name}</span>
              )}
              {disabled ? null : (
                <button
                  type="button"
                  onClick={() => toggle(name)}
                  aria-label={t("concept.remove", { name })}
                  className="rounded-full p-0.5 hover:bg-background/60"
                >
                  <X className="size-3" />
                </button>
              )}
            </Badge>
          ))
        )}
        {selected.length > MAX_VISIBLE_CHIPS ? (
          <Button variant="ghost" size="sm" onClick={() => setShowAllSelected((v) => !v)}>
            {showAllSelected
              ? t("common.showLess")
              : t("concept.more", { n: selected.length - MAX_VISIBLE_CHIPS })}
          </Button>
        ) : null}
        {selected.length > 1 && !disabled ? (
          <Button variant="ghost" size="sm" onClick={() => onChange([])}>
            {t("common.clear")}
          </Button>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            aria-label={t("concept.search")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("concept.search.placeholder")}
            className="pl-8"
          />
        </div>
        {grouped.length > 1 ? (
          <Button variant="ghost" size="sm" onClick={() => setAll(!anyOpen)}>
            {anyOpen ? t("concept.collapseAll") : t("concept.expandAll")}
          </Button>
        ) : null}
      </div>

      <div
        className="thin-scroll overflow-y-auto rounded-lg border border-border"
        style={{ maxHeight }}
      >
        {grouped.length === 0 ? (
          <p className="p-4 text-center text-body text-muted-foreground">{t("concept.noResults")}</p>
        ) : (
          grouped.map(([domain, items]) => {
            const picked = items.filter((concept) => chosen.has(concept.name)).length;
            const open = override[domain] ?? (searching || picked > 0);
            const colour = colours.get(domain);
            return (
              <div key={domain} className="border-b border-border last:border-b-0">
                <div className="sticky top-0 z-10 flex items-center gap-2 bg-muted/85 px-2 py-1.5 backdrop-blur">
                  <button
                    type="button"
                    onClick={() =>
                      setOverride((current) => ({ ...current, [domain]: !open }))
                    }
                    aria-expanded={open}
                    className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                  >
                    <ChevronRight
                      className={cn(
                        "size-3.5 shrink-0 text-muted-foreground transition-transform",
                        open && "rotate-90",
                      )}
                    />
                    <span
                      className="size-2 shrink-0 rounded-full"
                      style={{ background: colour }}
                    />
                    <span className="truncate text-small font-medium uppercase tracking-wide text-muted-foreground">
                      {domain}
                    </span>
                  </button>

                  <span
                    className={cn(
                      "shrink-0 text-small nums",
                      picked > 0 ? "font-medium text-primary" : "text-muted-foreground",
                    )}
                  >
                    {picked}/{items.length}
                  </span>
                  {disabled ? null : (
                    <button
                      type="button"
                      onClick={() => toggleDomain(items, picked === items.length)}
                      className="shrink-0 rounded px-1.5 py-0.5 text-small text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                    >
                      {picked === items.length ? "ninguno" : "todos"}
                    </button>
                  )}
                </div>

                {open ? (
                  <div className="flex flex-wrap gap-1.5 p-2">
                    {items.map((concept) => {
                      const isSelected = chosen.has(concept.name);
                      const zeroShot = showExemplarCount && concept.exemplars === 0;
                      return (
                        <button
                          key={concept.name}
                          type="button"
                          disabled={disabled}
                          onClick={() => toggle(concept.name)}
                          title={
                            showExemplarCount
                              ? zeroShot
                                ? t("concept.noExemplars")
                                : plural("concept.exemplars", concept.exemplars)
                              : undefined
                          }
                          className={cn(
                            "inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-small transition-colors",
                            isSelected
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-background hover:border-primary/50 hover:bg-accent",
                            disabled && "cursor-default opacity-70 hover:border-border hover:bg-background",
                          )}
                        >
                          <span className="truncate">{concept.name}</span>
                          {showExemplarCount ? (
                            zeroShot ? (
                              <span
                                className={cn(
                                  "size-1.5 shrink-0 rounded-full",
                                  isSelected
                                    ? "bg-primary-foreground/70"
                                    : "bg-attention",
                                )}
                              />
                            ) : (
                              <span
                                className={cn(
                                  "shrink-0 nums",
                                  isSelected
                                    ? "text-primary-foreground/70"
                                    : "text-muted-foreground",
                                )}
                              >
                                {concept.exemplars}
                              </span>
                            )
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
