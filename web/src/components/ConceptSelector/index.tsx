import { LayoutGrid, LayoutList, ListFilter, Search, Waypoints, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { useModalFocus } from "@/components/ui/focus";
import { Input } from "@/components/ui/input";
import { hasExemplars } from "@/lib/concepts";
import { domainColours } from "@/lib/domains";
import type { GraphView, KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BoardMode } from "./BoardMode";
import { GraphMode } from "./GraphMode";
import { SelectionTray } from "./SelectionTray";
import { useT } from "@/lib/i18n";

export interface ConceptSelectorProps {
  concepts: KgConcept[];
  graph: GraphView | undefined;
  selected: string[];
  onChange: (next: string[]) => void;
  /**
   * Concepts the graph places BEFORE what is already chosen. They are MARKED and remain
   * fully selectable (2026-09-04, explicit user request, reversing the lock of the same
   * week).
   *
   * The lock was a UI invention with nothing behind it: `KnowledgeGraph._closure` subtracts
   * the targets from the closure it returns, so choosing a prerequisite as a target is
   * exactly the commission the generator already computes — it stops being «se da por
   * sabido» and becomes one more objective. What the lock actually did was refuse ordinary
   * commissions («if» with «elif», «Recursividad» with «Función») and, being TRANSITIVE, do
   * it to concepts several hops away whose connection to the chosen one is invisible on the
   * board.
   *
   * It is disjoint from `selected` — `priors()` subtracts its own seeds — so a chosen
   * concept never draws the mark.
   */
  implied?: Set<string>;
  /** When given, only these are offered. It is the active curriculum. */
  restrictTo?: string[] | null;
  /**
   * Offer the exemplar SCOPE, and open in it. The selector then owns a two-way switch in
   * its header — «Con ejemplos», the default, keeps to the concepts the bank can
   * illustrate, prerequisites included; «Todos los conceptos» lifts it — and goes back to
   * the default every time it opens.
   */
  onlyWithExemplars?: boolean;
  /**
   * The modality being generated. Given, every exemplar count on screen is the count of
   * THAT modality, because it is the only one the few-shot block may draw from. Null when
   * the profile declares a single one, where the total already says it.
   */
  exemplarType?: string | null;
  /**
   * Choosing TARGETS keeps this false: a target is what an item is about, and only a
   * taggable concept can be that. Declaring COVERAGE passes it, because a curriculum may
   * legitimately contain non-taggable concepts.
   */
  allowNonTaggable?: boolean;
  title: string;
  open: boolean;
  /** Dismissing: the X and Escape. The selection is applied as it is made, so it keeps it. */
  onClose: () => void;
  /**
   * Being done. It defaults to `onClose` and exists because a caller that is a step in a
   * form wants the next step opened, which dismissing must not do.
   */
  onConfirm?: () => void;
  confirmLabel?: string;
}

type ViewMode = "board" | "graph";
type Scope = "exemplars" | "all";

export function ConceptSelector({
  concepts,
  graph,
  selected,
  onChange,
  implied,
  restrictTo,
  onlyWithExemplars = false,
  exemplarType = null,
  allowNonTaggable = false,
  title,
  open,
  onClose,
  onConfirm,
  confirmLabel,
}: ConceptSelectorProps) {
  const { t } = useT();
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewMode>("board");
  const [cursor, setCursor] = useState(0);
  const [scope, setScope] = useState<Scope>("exemplars");
  const panel = useRef<HTMLDivElement>(null);

  // THE DEFAULT IS THE BANK'S SIDE, EVERY TIME (2026-09-04, explicit user request): what a
  // person opens onto is the concepts with something to imitate, and lifting the scope is a
  // decision for one visit, not a setting.
  useEffect(() => {
    if (open) setScope("exemplars");
  }, [open]);

  const chosen = useMemo(() => new Set(selected), [selected]);
  const colours = useMemo(() => domainColours(concepts), [concepts]);
  const domainOf = useMemo(
    () => new Map(concepts.map((concept) => [concept.name, concept.domain])),
    [concepts],
  );

  // A FILTER THAT WOULD LEAVE NOTHING FILTERS NOTHING. On a bank whose items are all
  // untagged, or whose modality has no example yet, the exemplar scope would empty the
  // board outright; there it is not offered at all — no switch, no count — and everything
  // the caller's OWN restrictions allow is on the board, which is what «all» would show.
  const scopeOffered = useMemo(() => {
    if (!onlyWithExemplars) return false;
    const allowed = restrictTo && restrictTo.length > 0 ? new Set(restrictTo) : null;
    return concepts.some((concept) => {
      if (allowed && !allowed.has(concept.name)) return false;
      if (!concept.taggable && !allowNonTaggable) return false;
      return hasExemplars(concept, exemplarType);
    });
  }, [concepts, onlyWithExemplars, restrictTo, allowNonTaggable, exemplarType]);
  const filterByExemplars = scopeOffered && scope === "exemplars";

  // The one place that decides what state a concept is in. `selected` is shown always,
  // and every filter only decides what ELSE is offered — otherwise a concept a filter
  // stopped matching after it was chosen silently disappears from the screen while still
  // counting. Neither mode nor the tray may re-derive any part of this.
  //
  // A PREREQUISITE IS ONE MORE CONCEPT HERE (2026-09-04, explicit user request). It used to
  // have a branch of its own — drawn whatever the curriculum said, and never selectable —
  // and the whole branch existed to explain a lock that has no business existing (see
  // `implied` above). With the lock gone it follows the ordinary rules: the curriculum
  // bounds what may be a TARGET, and a prerequisite outside it is no more legitimate a
  // target than any other concept outside it.
  const state = useMemo(() => {
    const allowed = restrictTo && restrictTo.length > 0 ? new Set(restrictTo) : null;
    const visible: KgConcept[] = [];
    const selectable = new Set<string>();
    for (const concept of concepts) {
      const name = concept.name;
      if (!chosen.has(name)) {
        if (allowed && !allowed.has(name)) continue;
        if (!concept.taggable && !allowNonTaggable) continue;
        if (filterByExemplars && !hasExemplars(concept, exemplarType)) continue;
      }
      visible.push(concept);
      selectable.add(name);
    }
    return { visible, selectable };
  }, [concepts, restrictTo, filterByExemplars, exemplarType, allowNonTaggable, chosen]);

  // What the tray lists under «Vienen antes». Derived from the graph and NOT from the
  // board, because it states a fact about the choice — these come before what you picked —
  // and not about what happens to be on screen: a prerequisite the exemplar scope is
  // hiding is still one, and the tray is where somebody sees it without scrolling.
  const impliedNames = useMemo(
    () => (implied ? concepts.map((c) => c.name).filter((name) => implied.has(name)) : []),
    [concepts, implied],
  );
  const impliedSet = useMemo(() => new Set(impliedNames), [impliedNames]);

  // Concepts the EXEMPLAR scope alone is keeping out — not the curriculum and not
  // taggability, which are the caller's own restrictions and have their own wording.
  const hiddenByExemplars = useMemo(() => {
    if (!filterByExemplars) return 0;
    const allowed = restrictTo && restrictTo.length > 0 ? new Set(restrictTo) : null;
    return concepts.filter((concept) => {
      if (chosen.has(concept.name)) return false;
      if (hasExemplars(concept, exemplarType)) return false;
      if (!concept.taggable && !allowNonTaggable) return false;
      return !allowed || allowed.has(concept.name);
    }).length;
  }, [concepts, filterByExemplars, restrictTo, allowNonTaggable, exemplarType, chosen]);

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
    return [...byDomain.entries()];
  }, [state, query]);

  const flat = useMemo(
    () => grouped.flatMap(([, items]) => items.map((concept) => concept.name)),
    [grouped],
  );

  useEffect(() => {
    setCursor(0);
  }, [query, view]);

  // The same focus contract as `ui/dialog.tsx`, from the same place: in, trapped, and back
  // to whatever opened it. Escape is NOT delegated — this one stops the event on its own
  // container so a selector opened from inside another dialog closes itself and not both.
  useModalFocus(open, panel);

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
      ref={panel}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onKeyDown={onKeyDown}
      className="fixed inset-0 z-50 flex flex-col bg-background animate-fade-in"
    >
      <header className="shrink-0 border-b border-border bg-card/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-3">
          <h2 className="mr-auto min-w-0 truncate text-body font-semibold">{title}</h2>

          {/* Only the board is searchable. A graph whose nodes vanish as you type is not
              a graph any more, and this is a selector, not a search tool. */}
          {view === "board" ? (
            <div className="relative min-w-56 flex-1 sm:max-w-md">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                aria-label={t("concept.search")}
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("concept.search.placeholder")}
                className="pl-8"
              />
            </div>
          ) : null}

          {/* THE SCOPE IS A VISIBLE SWITCH, NOT A SETTING (2026-09-04, explicit user
              request). It sits beside the view switch because it is the same kind of
              control — how the syllabus is shown — and it is drawn only where the bank can
              illustrate something at all. */}
          {scopeOffered ? (
            <div
              role="group"
              aria-label={t("concept.scope.label")}
              className="flex items-center gap-1 rounded-md border border-border bg-background p-0.5"
            >
              {(
                [
                  {
                    value: "exemplars",
                    label: t("concept.scope.exemplars"),
                    icon: ListFilter,
                    hint: t("concept.scope.exemplarsHint"),
                  },
                  {
                    value: "all",
                    label: t("concept.scope.all"),
                    icon: LayoutList,
                    hint: t("concept.scope.allHint"),
                  },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  type="button"
                  title={option.hint}
                  aria-pressed={scope === option.value}
                  onClick={() => setScope(option.value)}
                  className={cn(
                    "flex items-center gap-1.5 rounded px-2.5 py-1 text-small font-medium transition-colors",
                    scope === option.value
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  <option.icon className="size-3.5" />
                  {option.label}
                </button>
              ))}
            </div>
          ) : null}

          <div className="flex items-center gap-1 rounded-md border border-border bg-background p-0.5">
            {(
              [
                {
                  value: "board",
                  label: t("concept.tab.list"),
                  icon: LayoutGrid,
                  hint: t("concept.tab.listHint"),
                },
                {
                  value: "graph",
                  label: t("concept.tab.graph"),
                  icon: Waypoints,
                  hint: t("concept.tab.graphHint"),
                },
              ] as const
            ).map((option) => (
              <button
                key={option.value}
                type="button"
                title={
                  option.value === "graph" && !graph
                    ? t("concept.noGraph")
                    : option.hint
                }
                disabled={option.value === "graph" && !graph}
                onClick={() => setView(option.value)}
                className={cn(
                  "flex items-center gap-1.5 rounded px-2.5 py-1 text-small font-medium transition-colors disabled:opacity-40",
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

          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label={t("common.close")}>
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
            onToggle={toggle}
            onAdd={addMany}
          />
        ) : (
          <BoardMode
            groups={grouped}
            chosen={chosen}
            selectable={state.selectable}
            implied={impliedSet}
            colours={colours}
            activeName={flat[cursor] ?? null}
            exemplarType={exemplarType}
            markMissingExemplars={onlyWithExemplars}
            onToggle={toggle}
            onToggleDomain={toggleDomain}
          />
        )}
      </div>

      <SelectionTray
        selected={selected}
        implied={impliedNames}
        total={state.selectable.size}
        colourFor={(name) => colours.get(domainOf.get(name) ?? "")}
        onRemove={toggle}
        onClear={() => onChange([])}
        onConfirm={onConfirm ?? onClose}
        confirmLabel={confirmLabel ?? t("concept.done")}
        hidden={hiddenByExemplars}
        onShowAll={() => setScope("all")}
      />
    </div>,
    document.body,
  );
}
