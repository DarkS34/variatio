import { LayoutGrid, Search, Waypoints, X } from "lucide-react";
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { domainColour } from "@/lib/format";
import type { GraphView, KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BoardMode } from "./BoardMode";
import { SelectionTray } from "./SelectionTray";

export interface ConceptSelectorProps {
  concepts: KgConcept[];
  graph: GraphView | undefined;
  selected: string[];
  onChange: (next: string[]) => void;
  /** Marked, dimmed and NOT selectable. They come in by prerequisite. */
  implied?: Set<string>;
  /** When given, only these are offered. It is the active curriculum. */
  restrictTo?: string[] | null;
  onlyWithExemplars?: boolean;
  showExemplarCount?: boolean;
  title: string;
  open: boolean;
  onClose: () => void;
}

type ViewMode = "board" | "graph";

function domainColours(concepts: KgConcept[]): Map<string, string> {
  const sizes = new Map<string, number>();
  for (const concept of concepts) {
    sizes.set(concept.domain, (sizes.get(concept.domain) ?? 0) + 1);
  }
  const ordered = [...sizes.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es"),
  );
  return new Map(ordered.map(([name], index) => [name, domainColour(index, ordered.length)]));
}

export function ConceptSelector({
  concepts,
  graph,
  selected,
  onChange,
  implied,
  restrictTo,
  onlyWithExemplars = false,
  showExemplarCount = true,
  title,
  open,
  onClose,
}: ConceptSelectorProps) {
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewMode>("board");
  const [cursor, setCursor] = useState(0);

  const chosen = useMemo(() => new Set(selected), [selected]);
  const colours = useMemo(() => domainColours(concepts), [concepts]);
  const domainOf = useMemo(
    () => new Map(concepts.map((concept) => [concept.name, concept.domain])),
    [concepts],
  );

  const offered = useMemo(() => {
    const allowed = restrictTo && restrictTo.length > 0 ? new Set(restrictTo) : null;
    return concepts.filter((concept) => {
      if (allowed && !allowed.has(concept.name)) return false;
      const kept =
        (allowed?.has(concept.name) ?? false) ||
        chosen.has(concept.name) ||
        (implied?.has(concept.name) ?? false);
      if (!concept.taggable && !kept) return false;
      if (onlyWithExemplars && concept.exemplars === 0 && !kept) return false;
      return true;
    });
  }, [concepts, restrictTo, onlyWithExemplars, chosen, implied]);

  const grouped = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = needle
      ? offered.filter(
          (concept) =>
            concept.name.toLowerCase().includes(needle) ||
            concept.domain.toLowerCase().includes(needle),
        )
      : offered;
    const byDomain = new Map<string, KgConcept[]>();
    for (const concept of matching) {
      const bucket = byDomain.get(concept.domain) ?? [];
      bucket.push(concept);
      byDomain.set(concept.domain, bucket);
    }
    return [...byDomain.entries()].sort((a, b) => a[0].localeCompare(b[0], "es"));
  }, [offered, query]);

  const flat = useMemo(
    () => grouped.flatMap(([, items]) => items.map((concept) => concept.name)),
    [grouped],
  );

  useEffect(() => {
    setCursor(0);
  }, [query, view]);

  useEffect(() => {
    if (!open) return;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [open]);

  if (!open) return null;

  const toggle = (name: string) => {
    if (implied?.has(name)) return;
    onChange(chosen.has(name) ? selected.filter((c) => c !== name) : [...selected, name]);
  };

  const toggleDomain = (items: KgConcept[], allChosen: boolean) => {
    const names = items.filter((item) => !implied?.has(item.name)).map((item) => item.name);
    if (allChosen) {
      const drop = new Set(names);
      onChange(selected.filter((c) => !drop.has(c)));
    } else {
      onChange([...selected, ...names.filter((name) => !chosen.has(name))]);
    }
  };

  const move = (step: number) => {
    if (flat.length === 0) return;
    setCursor((current) => (current + step + flat.length) % flat.length);
  };

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (view !== "board") return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      move(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      move(-1);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const name = flat[cursor];
      if (name) toggle(name);
    }
  };

  const impliedList = implied
    ? offered.filter((concept) => implied.has(concept.name)).map((concept) => concept.name)
    : [];

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onKeyDown={onKeyDown}
      className="fixed inset-0 z-50 flex flex-col bg-background animate-fade-in"
    >
      <header className="shrink-0 border-b border-border bg-card/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-3">
          <h2 className="mr-auto min-w-0 truncate text-sm font-semibold">{title}</h2>

          <div className="relative min-w-56 flex-1 sm:max-w-md">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar concepto o dominio…"
              className="pl-8"
            />
          </div>

          <div className="flex items-center gap-1 rounded-md border border-border bg-background p-0.5">
            {(
              [
                {
                  value: "board",
                  label: "Lista",
                  icon: LayoutGrid,
                  hint: "Los conceptos agrupados por dominio",
                },
                {
                  value: "graph",
                  label: "Grafo",
                  icon: Waypoints,
                  hint: "El grafo ordenado por niveles de prerrequisito",
                },
              ] as const
            ).map((option) => (
              <button
                key={option.value}
                type="button"
                title={
                  option.value === "graph" && !graph
                    ? "Este espacio de trabajo no tiene grafo que mostrar"
                    : option.hint
                }
                disabled={option.value === "graph"}
                onClick={() => setView(option.value)}
                className={cn(
                  "flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-40",
                  view === option.value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <option.icon className="size-3.5" />
                {option.label}
              </button>
            ))}
          </div>

          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Cerrar">
            <X />
          </Button>
        </div>
      </header>

      <div
        className={cn(
          "min-h-0 flex-1",
          view === "board" ? "thin-scroll overflow-y-auto" : "overflow-hidden",
        )}
      >
        <BoardMode
          groups={grouped}
          chosen={chosen}
          implied={implied}
          colours={colours}
          showExemplarCount={showExemplarCount}
          activeName={flat[cursor] ?? null}
          onToggle={toggle}
          onToggleDomain={toggleDomain}
        />
      </div>

      <SelectionTray
        selected={selected}
        implied={impliedList}
        total={offered.length}
        colourFor={(name) => colours.get(domainOf.get(name) ?? "")}
        onRemove={toggle}
        onClear={() => onChange([])}
      />
    </div>,
    document.body,
  );
}
