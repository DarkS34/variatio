import { useEffect, useRef } from "react";

import { hasExemplars } from "@/lib/concepts";
import type { KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export function BoardMode({
  groups,
  chosen,
  selectable,
  implied,
  colours,
  activeName,
  exemplarType = null,
  markMissingExemplars = false,
  onToggle,
  onToggleDomain,
}: {
  groups: [string, KgConcept[]][];
  chosen: Set<string>;
  /** Everything the selector is showing. Since 2026-09-04 a prerequisite is in it too. */
  selectable: Set<string>;
  /**
   * Concepts the graph places before what is already chosen. They are MARKED — dashed and
   * tinted, with a title saying so — and remain pickable: choosing one turns it into a
   * target, which is exactly what the generator computes for it (see `ConceptSelector`).
   */
  implied?: Set<string>;
  colours: Map<string, string>;
  activeName: string | null;
  exemplarType?: string | null;
  /**
   * Draw a concept with nothing to imitate as such — dashed, muted, its title saying so.
   * Under the «all» scope it is what tells a concept the bank illustrates from one it
   * does not; a chosen concept whose exemplars have gone since is marked the same way.
   */
  markMissingExemplars?: boolean;
  onToggle: (concept: string) => void;
  onToggleDomain: (items: KgConcept[], allChosen: boolean) => void;
}) {
  const { t } = useT();
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeName]);

  if (groups.length === 0) {
    return (
      <p className="p-16 text-center text-body text-muted-foreground">{t("concept.noResults")}</p>
    );
  }

  return (
    <div className="mx-auto grid max-w-[110rem] gap-4 p-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-3">
      {groups.map(([domain, items]) => {
        // Over the selectable chips. Since a prerequisite became pickable (2026-09-04) that
        // is every chip on the board, but the filter stays: it is what keeps «todos» from
        // claiming a total it cannot reach if anything ever stops being selectable again.
        const picked = items.filter((concept) => chosen.has(concept.name)).length;
        const free = items.filter((concept) => selectable.has(concept.name));
        const allChosen = free.length > 0 && free.every((concept) => chosen.has(concept.name));
        const colour = colours.get(domain);
        return (
          <section
            key={domain}
            className="flex flex-col overflow-hidden rounded-xl border border-border bg-card"
          >
            <header
              className="flex items-center gap-2 border-b border-border px-3 py-2"
              style={{
                background: colour
                  ? `color-mix(in oklch, ${colour} 12%, transparent)`
                  : undefined,
              }}
            >
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ background: colour }}
              />
              <h3 className="min-w-0 flex-1 truncate text-small font-semibold uppercase tracking-wide">
                {domain}
              </h3>
              <span
                className={cn(
                  "shrink-0 text-small nums",
                  picked > 0 ? "font-medium text-primary" : "text-muted-foreground",
                )}
              >
                {picked}/{free.length}
              </span>
              <button
                type="button"
                disabled={free.length === 0}
                onClick={() => onToggleDomain(free, allChosen)}
                className="shrink-0 rounded px-1.5 py-0.5 text-small text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40 disabled:hover:bg-transparent"
              >
                {allChosen ? "ninguno" : "todos"}
              </button>
            </header>

            <div className="flex flex-wrap content-start gap-1.5 p-3">
              {items.map((concept) => {
                const state = chosen.has(concept.name)
                  ? "selected"
                  : implied?.has(concept.name)
                    ? "prerequisite"
                    : "free";
                const isActive = activeName === concept.name;
                const noExemplar =
                  markMissingExemplars && !hasExemplars(concept, exemplarType);
                // TWO INDEPENDENT MARKS ON TWO CHANNELS, so a chip can carry both: the
                // GROUND says where the concept sits relative to what is chosen, the
                // BORDER STYLE says whether the bank can illustrate it. They used to share
                // one branch, so a prerequisite with no example reported only the first and
                // a CHOSEN concept whose exemplars had gone reported neither — which is
                // what this component's own `markMissingExemplars` already promised.
                const title =
                  [
                    state === "prerequisite" ? t("concept.byPrerequisite") : null,
                    noExemplar
                      ? exemplarType
                        ? t("concept.noExemplarsOfType")
                        : t("concept.noExemplars")
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || undefined;
                return (
                  <button
                    key={concept.name}
                    ref={isActive ? activeRef : undefined}
                    type="button"
                    onClick={() => onToggle(concept.name)}
                    title={title}
                    className={cn(
                      "relative inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-small transition-colors",
                      // A CHIP NEVER CHANGES WIDTH (2026-09-04, explicit user request:
                      // «que se quede donde está»). Both marks are the border and the
                      // ground and cost no inline space; a glyph used to sit in the corner
                      // and widened the chip by 18 px, re-wrapping nineteen of them.
                      state === "selected" && "border-primary bg-primary text-primary-foreground",
                      state === "prerequisite" &&
                        "border-primary/50 bg-primary/10 text-primary hover:bg-primary/20",
                      state === "free" &&
                        "border-border bg-background hover:border-primary/50 hover:bg-accent",
                      noExemplar && "border-dashed",
                      state === "free" && noExemplar && "text-muted-foreground",
                      isActive && "ring-2 ring-ring ring-offset-1 ring-offset-background",
                    )}
                  >
                    <span className="truncate">{concept.name}</span>
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
