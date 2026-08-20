import { LayoutGrid, Search, Waypoints, X } from "lucide-react";
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { domainColours } from "@/lib/domains";
import type { GraphView, KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BoardMode } from "./BoardMode";
import { GraphMode } from "./GraphMode";
import { SelectionTray } from "./SelectionTray";

export interface ConceptSelectorProps {
  concepts: KgConcept[];
  graph: GraphView | undefined;
  selected: string[];
  onChange: (next: string[]) => void;
  /**
   * Marked, dimmed and NOT selectable. They come in by prerequisite.
   *
   * It must be disjoint from `selected` — `priors()` subtracts its own seeds, which is what
   * makes it so for both current callers — because the counts are taken over the selectable
   * set, and a name in both would be subtracted from the total while still being counted as
   * chosen.
   */
  implied?: Set<string>;
  /** When given, only these are offered. It is the active curriculum. */
  restrictTo?: string[] | null;
  onlyWithExemplars?: boolean;
  /**
   * Choosing TARGETS keeps this false: a target is what an item is about, and only a
   * taggable concept can be that. Declaring COVERAGE passes it, because a curriculum may
   * legitimately contain non-taggable concepts.
   */
  allowNonTaggable?: boolean;
  showExemplarCount?: boolean;
  title: string;
  open: boolean;
  onClose: () => void;
}

type ViewMode = "board" | "graph";

export function ConceptSelector({
  concepts,
  graph,
  selected,
  onChange,
  implied,
  restrictTo,
  onlyWithExemplars = false,
  allowNonTaggable = false,
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

  // The one place that decides what state a concept is in. `implied` is shown always,
  // `selected` is shown always, and every filter only decides what ELSE is offered —
  // otherwise a prerequisite pulled in from outside the curriculum, or a concept a filter
  // stopped matching after it was chosen, silently disappears from the screen while still
  // counting. Neither mode nor the tray may re-derive any part of this.
  const state = useMemo(() => {
    const allowed = restrictTo && restrictTo.length > 0 ? new Set(restrictTo) : null;
    const visible: KgConcept[] = [];
    const selectable = new Set<string>();
    const impliedNames: string[] = [];
    for (const concept of concepts) {
      const name = concept.name;
      if (implied?.has(name)) {
        visible.push(concept);
        impliedNames.push(name);
        continue;
      }
      if (!chosen.has(name)) {
        if (allowed && !allowed.has(name)) continue;
        if (!concept.taggable && !allowNonTaggable) continue;
        if (onlyWithExemplars && concept.exemplars === 0) continue;
      }
      visible.push(concept);
      selectable.add(name);
    }
    return { visible, selectable, impliedNames };
  }, [concepts, restrictTo, onlyWithExemplars, allowNonTaggable, chosen, implied]);

  const grouped = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = needle
      ? state.visible.filter(
          (concept) =>
            concept.name.toLowerCase().includes(needle) ||
            concept.domain.toLowerCase().includes(needle),
        )
      : state.visible;
    const byDomain = new Map<string, KgConcept[]>();
    for (const concept of matching) {
      const bucket = byDomain.get(concept.domain) ?? [];
      bucket.push(concept);
      byDomain.set(concept.domain, bucket);
    }
    return [...byDomain.entries()].sort((a, b) => a[0].localeCompare(b[0], "es"));
  }, [state, query]);

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
    if (!state.selectable.has(name)) return;
    onChange(chosen.has(name) ? selected.filter((c) => c !== name) : [...selected, name]);
  };

  const toggleDomain = (items: KgConcept[], allChosen: boolean) => {
    const names = items.filter((item) => state.selectable.has(item.name)).map((item) => item.name);
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

  const addMany = (names: string[]) => {
    const extra = names.filter((name) => !chosen.has(name) && state.selectable.has(name));
    if (extra.length > 0) onChange([...selected, ...extra]);
  };

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

          {/* Only the board is searchable. A graph whose nodes vanish as you type is not
              a graph any more, and this is a selector, not a search tool. */}
          {view === "board" ? (
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
          ) : null}

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
                disabled={option.value === "graph" && !graph}
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
        {view === "graph" && graph ? (
          <GraphMode
            graph={graph}
            selectable={state.selectable}
            chosen={chosen}
            implied={implied}
            onToggle={toggle}
            onAdd={addMany}
          />
        ) : (
          <BoardMode
            groups={grouped}
            chosen={chosen}
            selectable={state.selectable}
            colours={colours}
            showExemplarCount={showExemplarCount}
            activeName={flat[cursor] ?? null}
            onToggle={toggle}
            onToggleDomain={toggleDomain}
          />
        )}
      </div>

      <SelectionTray
        selected={selected}
        implied={state.impliedNames}
        total={state.selectable.size}
        colourFor={(name) => colours.get(domainOf.get(name) ?? "")}
        onRemove={toggle}
        onClear={() => onChange([])}
      />
    </div>,
    document.body,
  );
}
