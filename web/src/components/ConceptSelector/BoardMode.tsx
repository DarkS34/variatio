import { Lock } from "lucide-react";
import { useEffect, useRef } from "react";

import type { KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";

export function BoardMode({
  groups,
  chosen,
  selectable,
  colours,
  showExemplarCount,
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
  activeName: string | null;
  onToggle: (concept: string) => void;
  onToggleDomain: (items: KgConcept[], allChosen: boolean) => void;
}) {
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeName]);

  if (groups.length === 0) {
    return (
      <p className="p-16 text-center text-sm text-muted-foreground">Sin resultados</p>
    );
  }

  return (
    <div className="mx-auto grid max-w-[110rem] gap-4 p-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-3">
      {groups.map(([domain, items]) => {
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
              <h3 className="min-w-0 flex-1 truncate text-xs font-semibold uppercase tracking-wide">
                {domain}
              </h3>
              <span
                className={cn(
                  "shrink-0 text-[11px] tabular-nums",
                  picked > 0 ? "font-medium text-primary" : "text-muted-foreground",
                )}
              >
                {picked}/{items.length}
              </span>
              <button
                type="button"
                disabled={free.length === 0}
                onClick={() => onToggleDomain(free, allChosen)}
                className="shrink-0 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40 disabled:hover:bg-transparent"
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
                const zeroShot = showExemplarCount && concept.exemplars === 0;
                return (
                  <button
                    key={concept.name}
                    ref={isActive ? activeRef : undefined}
                    type="button"
                    disabled={state === "implied"}
                    onClick={() => onToggle(concept.name)}
                    title={
                      state === "implied"
                        ? "Viene incluido por prerrequisito de lo que ya has elegido"
                        : showExemplarCount
                          ? zeroShot
                            ? "Sin ejemplos en el banco: se generará en zero-shot"
                            : `${concept.exemplars} ejemplo(s) en el banco`
                          : undefined
                    }
                    className={cn(
                      "inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
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
                              : "bg-[var(--warning)]",
                          )}
                        />
                      ) : (
                        <span
                          className={cn(
                            "shrink-0 tabular-nums",
                            state === "selected"
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
          </section>
        );
      })}
    </div>
  );
}
