import { Lock } from "lucide-react";
import { useEffect, useRef } from "react";

import { exemplarCount } from "@/lib/concepts";
import type { KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export function BoardMode({
  groups,
  chosen,
  selectable,
  colours,
  showExemplarCount,
  exemplarType,
  activeName,
  onToggle,
  onToggleDomain,
}: {
  groups: [string, KgConcept[]][];
  chosen: Set<string>;
  /** Everything the selector is showing minus what came in by prerequisite. */
  selectable: Set<string>;
  colours: Map<string, string>;
  showExemplarCount: boolean;
  exemplarType: string | null;
  activeName: string | null;
  onToggle: (concept: string) => void;
  onToggleDomain: (items: KgConcept[], allChosen: boolean) => void;
}) {
  const { t, plural } = useT();
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
        // Over the free chips, never over `items`: a locked prerequisite is neither pickable
        // nor countable, so including it in the denominator made «todos» stop short of the
        // total it had just claimed, and disagreed with the tray's own count.
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
                  "shrink-0 text-micro nums",
                  picked > 0 ? "font-medium text-primary" : "text-muted-foreground",
                )}
              >
                {picked}/{free.length}
              </span>
              <button
                type="button"
                disabled={free.length === 0}
                onClick={() => onToggleDomain(free, allChosen)}
                className="shrink-0 rounded px-1.5 py-0.5 text-micro text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40 disabled:hover:bg-transparent"
              >
                {allChosen ? "ninguno" : "todos"}
              </button>
            </header>

            <div className="flex flex-wrap content-start gap-1.5 p-3">
              {items.map((concept) => {
                const state = !selectable.has(concept.name)
                  ? "implied"
                  : chosen.has(concept.name)
                    ? "selected"
                    : "free";
                const isActive = activeName === concept.name;
                const count = exemplarCount(concept, exemplarType);
                const zeroShot = showExemplarCount && count === 0;
                return (
                  <button
                    key={concept.name}
                    ref={isActive ? activeRef : undefined}
                    type="button"
                    disabled={state === "implied"}
                    onClick={() => onToggle(concept.name)}
                    title={
                      state === "implied"
                        ? t("concept.byPrerequisite")
                        : showExemplarCount
                          ? zeroShot
                            ? exemplarType
                              ? t("concept.noExemplarsOfType")
                              : t("concept.noExemplars")
                            : exemplarType
        ? plural("concept.exemplarsOfType", count)
        : plural("concept.exemplars", count)
                          : undefined
                    }
                    className={cn(
                      "inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-small transition-colors",
                      state === "selected" && "border-primary bg-primary text-primary-foreground",
                      state === "implied" &&
                        "cursor-not-allowed border-dashed border-primary/40 bg-primary/10 text-primary/70",
                      state === "free" &&
                        "border-border bg-background hover:border-primary/50 hover:bg-accent",
                      isActive && "ring-2 ring-ring ring-offset-1 ring-offset-background",
                    )}
                  >
                    {state === "implied" ? <Lock className="size-3 shrink-0" /> : null}
                    <span className="truncate">{concept.name}</span>
                    {showExemplarCount && state !== "implied" ? (
                      zeroShot ? (
                        <span
                          className={cn(
                            "size-1.5 shrink-0 rounded-full",
                            state === "selected"
                              ? "bg-primary-foreground/70"
                              : "bg-attention",
                          )}
                        />
                      ) : (
                        <span
                          className={cn(
                            "shrink-0 nums",
                            state === "selected"
                              ? "text-primary-foreground/70"
                              : "text-muted-foreground",
                          )}
                        >
                          {count}
                        </span>
                      )
                    ) : null}
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
